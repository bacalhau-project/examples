#!/bin/bash

set -euo pipefail

print_usage() {
    echo "Usage:"
    echo "  $0 create <name>        - Creates a new FIFO queue and associated IAM resources"
    echo "  $0 creds <name>         - Creates new credentials for existing queue"
    echo "  $0 delete <name>        - Deletes queue and all associated resources"
    echo "  $0 list                 - Lists all queues and their information in all regions"
    echo "  $0 find <name>          - Finds a specific queue across all regions"
    echo ""
    echo "Example:"
    echo "  $0 create scale-tester  - Creates scale-tester-events.fifo queue"
    echo "  $0 creds scale-tester   - Creates new credentials for scale-tester"
    echo "  $0 delete scale-tester  - Deletes scale-tester queue and resources"
    echo "  $0 list                 - Shows information about all queues in all regions"
    echo "  $0 find my-queue        - Finds my-queue in any region"
}

create_resources() {
    local base_name="$1"
    local queue_name="${base_name}-events.fifo"
    local user_name="${base_name}-event-handler"
    local policy_name="${base_name}-handler-policy"

    echo "Creating FIFO queue '${queue_name}'..."
    aws sqs create-queue \
        --queue-name "${queue_name}" \
        --attributes FifoQueue=true,ContentBasedDeduplication=true

    echo "Getting queue ARN..."
    local queue_arn
    queue_arn=$(aws sqs get-queue-attributes \
        --queue-url "https://sqs.$(aws configure get region).amazonaws.com/$(aws sts get-caller-identity --query Account --output text)/${queue_name}" \
        --attribute-names QueueArn \
        --query 'Attributes.QueueArn' \
        --output text)

    echo "Creating IAM user '${user_name}'..."
    aws iam create-user --user-name "${user_name}"

    echo "Creating IAM policy..."
    cat << EOF > /tmp/sqs-policy.json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:GetQueueUrl",
                "sqs:GetQueueAttributes",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:ListQueues",
                "sqs:PurgeQueue"
            ],
            "Resource": "${queue_arn}"
        }
    ]
}
EOF

    aws iam create-policy \
        --policy-name "${policy_name}" \
        --policy-document file:///tmp/sqs-policy.json

    echo "Attaching policy to user..."
    aws iam attach-user-policy \
        --user-name "${user_name}" \
        --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/${policy_name}"

    create_credentials "${base_name}"
}

delete_old_access_keys() {
    local user_name="$1"
    echo "Checking for existing access keys..."
    
    # List and delete existing access keys
    local existing_keys
    existing_keys=$(aws iam list-access-keys --user-name "${user_name}" --query 'AccessKeyMetadata[*].AccessKeyId' --output text)
    
    if [ -n "$existing_keys" ]; then
        echo "Found existing access keys. Deleting them..."
        for key_id in $existing_keys; do
            echo "Deleting access key: $key_id"
            aws iam delete-access-key --user-name "${user_name}" --access-key-id "$key_id"
        done
    fi
}

create_credentials() {
    local base_name="$1"
    local user_name="${base_name}-event-handler"
    
    # Delete old access keys first
    delete_old_access_keys "${user_name}"

    echo "Creating new access keys..."
    local creds
    creds=$(aws iam create-access-key --user-name "${user_name}")
    
    echo "Getting queue URL..."
    local queue_url
    queue_url=$(aws sqs get-queue-url \
        --queue-name "${base_name}-events.fifo" \
        --query 'QueueUrl' \
        --output text)

    echo ""
    echo "=== Configuration Details ==="
    echo "Add these to your .env file:"
    echo ""
    echo "AWS_ACCESS_KEY_ID=$(echo "$creds" | jq -r .AccessKey.AccessKeyId)"
    echo "AWS_SECRET_ACCESS_KEY=$(echo "$creds" | jq -r .AccessKey.SecretAccessKey)"
    echo "AWS_DEFAULT_REGION=$(aws configure get region)"
    echo "SQS_QUEUE_URL=${queue_url}"
    echo ""
    echo "=== End Configuration Details ==="
}

delete_resources() {
    local base_name="$1"
    local queue_name="${base_name}-events.fifo"
    local user_name="${base_name}-event-handler"
    local policy_name="${base_name}-handler-policy"

    echo "Getting account ID..."
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text)

    echo "Deleting queue '${queue_name}'..."
    aws sqs delete-queue --queue-url "https://sqs.$(aws configure get region).amazonaws.com/${account_id}/${queue_name}" || echo "Queue already deleted or not found"

    echo "Listing and deleting access keys for user..."
    aws iam list-access-keys --user-name "${user_name}" | \
        jq -r '.AccessKeyMetadata[].AccessKeyId' | \
        while read -r keyid; do
            echo "Deleting access key ${keyid}..."
            aws iam delete-access-key --user-name "${user_name}" --access-key-id "${keyid}"
        done || echo "No access keys found"

    echo "Detaching policies from user..."
    aws iam detach-user-policy \
        --user-name "${user_name}" \
        --policy-arn "arn:aws:iam::${account_id}:policy/${policy_name}" || echo "Policy already detached"

    echo "Deleting user '${user_name}'..."
    aws iam delete-user --user-name "${user_name}" || echo "User already deleted"

    echo "Deleting policy..."
    aws iam delete-policy \
        --policy-arn "arn:aws:iam::${account_id}:policy/${policy_name}" || echo "Policy already deleted"

    echo "Cleanup complete!"
}

list_queues() {
    echo "Fetching queues from all regions..."
    echo ""

    # Get list of all regions
    local regions
    regions=$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)

    for region in $regions; do
        echo "=== Region: $region ==="
        
        # Get all queue URLs in this region
        local queue_urls
        queue_urls=$(aws sqs list-queues --region "$region" --query 'QueueUrls[]' --output text || echo "")
        
        # Handle empty response or "None" response
        if [ -z "$queue_urls" ] || [ "$queue_urls" = "None" ]; then
            echo "No queues found in $region"
            echo "---"
            continue
        fi

        # Process each queue URL, skipping if it's "None"
        echo "$queue_urls" | while read -r url; do
            [ -z "$url" ] || [ "$url" = "None" ] && continue
            
            echo "Queue: $(basename "$url")"
            echo "URL: $url"
            
            # Get queue attributes
            local attrs
            attrs=$(aws sqs get-queue-attributes \
                --region "$region" \
                --queue-url "$url" \
                --attribute-names \
                    ApproximateNumberOfMessages \
                    ApproximateNumberOfMessagesNotVisible \
                    LastModifiedTimestamp \
                    CreatedTimestamp \
                    FifoQueue \
                    ContentBasedDeduplication \
                --output json 2>/dev/null || echo "{}")
            
            # Skip if we couldn't get attributes
            if [ "$(echo "$attrs" | jq -r 'has("Attributes")')" != "true" ]; then
                echo "Could not get attributes for queue"
                echo "---"
                continue
            fi
            
            echo "Messages Available: $(echo "$attrs" | jq -r '.Attributes.ApproximateNumberOfMessages')"
            echo "Messages In Flight: $(echo "$attrs" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')"
            
            # Convert timestamps to human readable format
            local created
            created=$(echo "$attrs" | jq -r '.Attributes.CreatedTimestamp')
            local modified
            modified=$(echo "$attrs" | jq -r '.Attributes.LastModifiedTimestamp')
            
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS date command
                echo "Created: $(date -r "$created")"
                echo "Last Modified: $(date -r "$modified")"
            else
                # GNU date command
                echo "Created: $(date -d @"$created")"
                echo "Last Modified: $(date -d @"$modified")"
            fi
            echo "FIFO Queue: $(echo "$attrs" | jq -r '.Attributes.FifoQueue // "false"')"
            echo "Content Deduplication: $(echo "$attrs" | jq -r '.Attributes.ContentBasedDeduplication // "false"')"
            echo "---"
        done
    done
}

# Add a new function to get a specific queue's info from any region
find_queue() {
    local queue_name="$1"
    echo "Searching for queue '$queue_name' in all regions..."
    echo ""

    # Get list of all regions
    local regions
    regions=$(aws ec2 describe-regions --query 'Regions[].RegionName' --output text)

    for region in $regions; do
        echo "Checking region: $region"
        
        # Try to get queue URL
        local queue_url
        queue_url=$(aws sqs get-queue-url --region "$region" --queue-name "$queue_name" --query 'QueueUrl' --output text 2>/dev/null || echo "")
        
        if [ -n "$queue_url" ] && [ "$queue_url" != "None" ]; then
            echo "Found queue in $region!"
            echo "URL: $queue_url"
            
            # Get queue attributes
            local attrs
            attrs=$(aws sqs get-queue-attributes \
                --region "$region" \
                --queue-url "$queue_url" \
                --attribute-names \
                    ApproximateNumberOfMessages \
                    ApproximateNumberOfMessagesNotVisible \
                    LastModifiedTimestamp \
                    CreatedTimestamp \
                    FifoQueue \
                    ContentBasedDeduplication \
                --output json)
            
            echo "Messages Available: $(echo "$attrs" | jq -r '.Attributes.ApproximateNumberOfMessages')"
            echo "Messages In Flight: $(echo "$attrs" | jq -r '.Attributes.ApproximateNumberOfMessagesNotVisible')"
            
            local created
            created=$(echo "$attrs" | jq -r '.Attributes.CreatedTimestamp')
            local modified
            modified=$(echo "$attrs" | jq -r '.Attributes.LastModifiedTimestamp')
            
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "Created: $(date -r "$created")"
                echo "Last Modified: $(date -r "$modified")"
            else
                echo "Created: $(date -d @"$created")"
                echo "Last Modified: $(date -d @"$modified")"
            fi
            echo "FIFO Queue: $(echo "$attrs" | jq -r '.Attributes.FifoQueue // "false"')"
            echo "Content Deduplication: $(echo "$attrs" | jq -r '.Attributes.ContentBasedDeduplication // "false"')"
            return 0
        fi
    done
    
    echo "Queue '$queue_name' not found in any region"
    return 1
}

main() {
    if [ $# -lt 1 ]; then
        print_usage
        exit 1
    fi

    local command="$1"
    case "${command}" in
        create)
            [ $# -lt 2 ] && { print_usage; exit 1; }
            create_resources "$2"
            ;;
        creds)
            [ $# -lt 2 ] && { print_usage; exit 1; }
            create_credentials "$2"
            ;;
        delete)
            [ $# -lt 2 ] && { print_usage; exit 1; }
            delete_resources "$2"
            ;;
        list)
            list_queues
            ;;
        find)
            [ $# -lt 2 ] && { print_usage; exit 1; }
            find_queue "$2"
            ;;
        *)
            print_usage
            exit 1
            ;;
    esac
}

main "$@"