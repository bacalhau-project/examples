#!/usr/bin/env bash
# spot-instances.sh
#
# Script to launch and manage AWS spot instances
set -e

source ./aws-spot-env.sh

# Debug settings
DEBUG=false
DEBUG_FILE="/tmp/spot_instance_debug.txt"

function debug() {
    if [ "$DEBUG" = true ]; then
        echo "[DEBUG] $(date '+%Y-%m-%d %H:%M:%S'): $1" >> "$DEBUG_FILE"
    fi
}

function list_instances() {
    echo "Listing instances with tag '${INSTANCE_TAG_KEY}=${INSTANCE_TAG_VALUE}'..."
    aws ec2 describe-instances \
        --region "$AWS_REGION" \
        --filters "Name=tag:${INSTANCE_TAG_KEY},Values=${INSTANCE_TAG_VALUE}" \
                 "Name=instance-state-name,Values=pending,running" \
        --output json \
        --query 'Reservations[].Instances[].[InstanceId,InstanceType,State.Name,LaunchTime,PublicDnsName]' \
        | jq -r '.[] | @tsv' \
        | column -t
}

function terminate_instance() {
    local instance_id="$1"
    echo "Terminating instance: $instance_id"
    aws ec2 terminate-instances --output json \
        --region "$AWS_REGION" \
        --instance-ids "$instance_id"
    
    echo "Waiting for instance to terminate..."
    while true; do
        status=$(aws ec2 describe-instances \
            --region "$AWS_REGION" \
            --instance-ids "$instance_id" \
            --output json \
            --query 'Reservations[].Instances[].State.Name' | jq -r '.[0]')
        
        if [ "$status" = "terminated" ] || [ -z "$status" ]; then
            break
        fi
        echo "Current status: $status"
        sleep 5
    done
    
    echo "Instance $instance_id has been terminated."
}

function terminate_all_instances() {
    local instance_ids=$(aws ec2 describe-instances \
        --region "$AWS_REGION" \
        --filters "Name=tag:${INSTANCE_TAG_KEY},Values=${INSTANCE_TAG_VALUE}" \
                 "Name=instance-state-name,Values=pending,running" \
        --output json \
        --query 'Reservations[].Instances[].InstanceId' \
        | jq -r '.[]')
    
    if [ -z "$instance_ids" ]; then
        echo "No running instances found matching tag '${INSTANCE_TAG_KEY}=${INSTANCE_TAG_VALUE}'."
        return
    fi
    
    echo "The following instances will be terminated:"
    list_instances
    
    read -p "Are you sure you want to terminate these instances? (y/N) " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        echo "Terminating instances..."
        aws ec2 terminate-instances --output json \
            --region "$AWS_REGION" \
            --instance-ids $instance_ids
        
        echo "Waiting for all instances to terminate..."
        while true; do
            statuses=$(aws ec2 describe-instances \
                --region "$AWS_REGION" \
                --instance-ids $instance_ids \
                --output json \
                --query 'Reservations[].Instances[].State.Name' | jq -r '.[]')
            
            # Check if all instances are terminated
            all_terminated=true
            for status in $statuses; do
                if [ "$status" != "terminated" ]; then
                    all_terminated=false
                    break
                fi
            done
            
            if [ "$all_terminated" = true ] || [ -z "$statuses" ]; then
                break
            fi
            
            echo "Current statuses: $statuses"
            sleep 5
        done
        
        echo "All matching instances have been terminated."
    else
        echo "Operation cancelled."
    fi
}

function ensure_security_group() {
    debug "Checking for existing security group..."
    # First try to get existing group
    local security_group_id=""
    local result=$(aws ec2 describe-security-groups \
        --region "$AWS_REGION" \
        --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
        --query 'SecurityGroups[0].GroupId' \
        --output text)

    debug "Query result: '$result'"

    if [ "$result" == "None" ] || [ -z "$result" ]; then
        debug "Creating security group: $SECURITY_GROUP_NAME"
        result=$(aws ec2 create-security-group \
            --region "$AWS_REGION" \
            --group-name "$SECURITY_GROUP_NAME" \
            --description "$SECURITY_GROUP_DESC" \
            --query 'GroupId' \
            --output text)
        debug "Created security group ID: '$result'"
    fi

    if [ -z "$result" ] || [ "$result" == "None" ]; then
        debug "Error: Failed to get or create security group"
        return 1
    fi

    security_group_id="$result"
    debug "Using security group ID: '$security_group_id'"

    # Remove existing ingress rules
    debug "Removing existing security group rules..."
    local existing_rules=$(aws ec2 describe-security-group-rules \
        --region "$AWS_REGION" \
        --filters "Name=group-id,Values=$security_group_id" \
        --query 'SecurityGroupRules[?!IsEgress].SecurityGroupRuleId' \
        --output text)
    
    if [ ! -z "$existing_rules" ]; then
        debug "Found existing rules: $existing_rules"
        for rule_id in $existing_rules; do
            debug "Revoking rule: $rule_id"
            aws ec2 revoke-security-group-ingress \
                --region "$AWS_REGION" \
                --group-id "$security_group_id" \
                --security-group-rule-ids "$rule_id" > /dev/null || true
        done
    fi

    debug "Configuring security group rules for ID: $security_group_id"
    # Add SSH access
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$security_group_id" \
        --protocol tcp \
        --port 22 \
        --cidr "0.0.0.0/0" > /dev/null || {
            debug "Failed to add SSH rule, might already exist"
        }

    # Add port 4222 access
    aws ec2 authorize-security-group-ingress \
        --region "$AWS_REGION" \
        --group-id "$security_group_id" \
        --protocol tcp \
        --port 4222 \
        --cidr "0.0.0.0/0" > /dev/null || {
            debug "Failed to add port 4222 rule, might already exist"
        }

    if [ -z "$security_group_id" ] || [ "$security_group_id" == "None" ]; then
        debug "Error: Security group ID is empty or None"
        return 1
    fi

    debug "Returning security group ID: '$security_group_id'"
    echo "$security_group_id"
}

function launch_instances() {
    # Get security group ID
    debug "Getting security group..."
    local security_group_id
    security_group_id=$(ensure_security_group)
    debug "Received security group ID: '$security_group_id'"
    
    if [ -z "$security_group_id" ] || [ "$security_group_id" == "None" ]; then
        echo "Error: Failed to get security group ID"
        exit 1
    fi
    
    debug "Security group ID before launch: '$security_group_id'"
    
    # Use the configured AMI - fail if not available
    local ami_id="$CONFIGURED_AMI_ID"
    if [ -z "$ami_id" ] || [ "$ami_id" == "null" ]; then
        echo "Error: No configured AMI found. Please run './build-ami.sh' first to create the AMI."
        exit 1
    fi
    
    debug "Using configured AMI ID: $ami_id"
    
    # Launch a single instance
    echo "Launching spot instance..."
    debug "Command: aws ec2 run-instances with spot options"
    
    local aws_debug=""
    if [ "$DEBUG" = true ]; then
        aws_debug="--debug"
    fi

    # Create a temporary file for error output
    local error_file=$(mktemp)
    
    # Launch spot instance
    local output
    if ! output=$(aws ec2 run-instances \
        --region "$AWS_REGION" \
        --image-id "$ami_id" \
        --instance-type "$INSTANCE_TYPE" \
        --key-name "$KEY_NAME" \
        --security-group-ids "$security_group_id" \
        --tag-specifications "ResourceType=instance,Tags=[{Key=$INSTANCE_TAG_KEY,Value=$INSTANCE_TAG_VALUE}]" \
        --iam-instance-profile "Name=BacalhauScaleTestRole" \
        --user-data "file://scripts/startup.sh" \
        --instance-market-options '{"MarketType":"spot","SpotOptions":{"SpotInstanceType":"one-time","InstanceInterruptionBehavior":"terminate"}}' \
        --count "$SPOT_INSTANCE_COUNT" \
        --output json \
        $aws_debug 2>"$error_file"); then
        
        echo "Error launching spot instance:"
        cat "$error_file"
        rm "$error_file"
        exit 1
    fi

    # Print launched instance details
    local instance_ids=$(echo "$output" | jq -r '.Instances[].InstanceId')
    echo "Successfully launched spot instances: $instance_ids"
    
    # Wait for instances to be running
    echo "Waiting for instances to be running..."
    while true; do
        local statuses=$(aws ec2 describe-instances \
            --region "$AWS_REGION" \
            --instance-ids $instance_ids \
            --output json \
            --query 'Reservations[].Instances[].[InstanceId,State.Name]' | \
            jq -r '.[] | @tsv')
        
        echo "Instance statuses:"
        echo "$statuses" | column -t
        
        if ! echo "$statuses" | grep -qE "pending|starting"; then
            break
        fi
        sleep 5
    done
    
    echo "Spot instances are now running. Use './spot-instances.sh list' to see details."
}

function show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  launch              Launch new spot instances (count: $SPOT_INSTANCE_COUNT)"
    echo "  list                List all running instances"
    echo "  terminate <id>      Terminate specific instance"
    echo "  terminate-all       Terminate all instances"
    echo "  help               Show this help message"
    echo ""
    echo "Options:"
    echo "  --debug            Enable debug output to $DEBUG_FILE"
}

# Main script logic
# Process command line arguments
COMMAND=""
for arg in "$@"; do
    case "$arg" in
        --debug)
            DEBUG=true
            # Clear debug file at start
            > "$DEBUG_FILE"
            ;;
        *)
            if [ -z "$COMMAND" ]; then
                COMMAND="$arg"
            fi
            ;;
    esac
done

case "$COMMAND" in
    launch)
        launch_instances
        ;;
    list)
        list_instances
        ;;
    terminate)
        if [ -z "$2" ]; then
            echo "Error: Instance ID required"
            show_usage
            exit 1
        fi
        terminate_instance "$2"
        ;;
    terminate-all)
        terminate_all_instances
        ;;
    help|--help|-h|"")
        show_usage
        ;;
    *)
        echo "Error: Unknown command '$1'"
        show_usage
        exit 1
        ;;
esac 