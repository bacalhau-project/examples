#!/usr/bin/env bash

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Check if required environment variables are set
if [ -z "$AWS_REGION" ] || [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$SQS_QUEUE_URL" ]; then
    echo "Error: Required AWS environment variables are not set"
    echo "Please ensure AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and SQS_QUEUE_URL are set in .env file"
    exit 1
fi

# Query SQS queue for messages
echo "Querying SQS queue: $SQS_QUEUE_URL"
aws sqs receive-message \
    --queue-url "$SQS_QUEUE_URL" \
    --attribute-names All \
    --message-attribute-names All \
    --max-number-of-messages 10 \
    --visibility-timeout 30 \
    --wait-time-seconds 20 \
    --region "$AWS_REGION" \
    --output json | jq -r '.Messages[] | "Message ID: \(.MessageId)\nBody: \(.Body)\n---"'

# Check if the command was successful
if [ $? -eq 0 ]; then
    echo "Query completed successfully"
else
    echo "Error: Failed to query SQS queue"
    exit 1
fi 