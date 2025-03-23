#!/bin/bash
# SQS Queue Inspector
# This script inspects the configuration and status of an SQS queue

# Configuration
REGION="us-east-2"
QUEUE_URL="https://sqs.us-east-2.amazonaws.com/767397752906/scale-tester-events.fifo"
# Note: We're using environment variables for credentials to avoid hardcoding them in scripts

# Don't attempt to use credentials from config.yaml when SSO is in use
echo "Using your existing AWS credentials from SSO or environment variables..."
# We're relying on credentials from SSO or AWS CLI configuration

export AWS_DEFAULT_REGION=$REGION

# Check if there's an active AWS SSO profile
SSO_PROFILE=""
if [ -n "$AWS_PROFILE" ]; then
  SSO_PROFILE="--profile $AWS_PROFILE"
  echo "Using AWS profile: $AWS_PROFILE"
fi

# Function to run AWS CLI commands with proper error handling
run_aws_command() {
  echo -e "\n========== $1 =========="
  shift
  # Use the SSO profile if it exists
  if [ -n "$SSO_PROFILE" ]; then
    aws "$SSO_PROFILE" "$@" || echo "ERROR: Command failed"
  else
    aws "$@" || echo "ERROR: Command failed"
  fi
}

# Print script header
echo "=================================================="
echo "SQS Queue Inspector - $(date)"
echo "Queue URL: $QUEUE_URL"
echo "=================================================="

# Extract queue name from URL
QUEUE_NAME=$(echo $QUEUE_URL | awk -F/ '{print $NF}')
ACCOUNT_ID=$(echo $QUEUE_URL | awk -F/ '{print $(NF-1)}')

# 1. Get queue attributes with all details
run_aws_command "QUEUE ATTRIBUTES" sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names All

# 2. List queue tags (if any)
run_aws_command "QUEUE TAGS" sqs list-queue-tags \
  --queue-url $QUEUE_URL

# 3. Get current approximate number of messages
run_aws_command "QUEUE MESSAGE COUNTS" sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible ApproximateNumberOfMessagesDelayed

# 4. Check if Dead Letter Queue is configured
run_aws_command "DEAD LETTER QUEUE CONFIG" sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names RedrivePolicy

# 5. Check if server-side encryption is enabled
run_aws_command "ENCRYPTION SETTINGS" sqs get-queue-attributes \
  --queue-url $QUEUE_URL \
  --attribute-names KmsMasterKeyId KmsDataKeyReusePeriodSeconds

# 6. List all queues in the region for reference
run_aws_command "ALL QUEUES IN REGION" sqs list-queues

# 7. For FIFO queues - check content-based deduplication setting
if [[ "$QUEUE_NAME" == *".fifo" ]]; then
  run_aws_command "FIFO QUEUE SETTINGS" sqs get-queue-attributes \
    --queue-url $QUEUE_URL \
    --attribute-names ContentBasedDeduplication FifoQueue

  echo -e "\n========== FIFO QUEUE DETAILS =========="
  echo "This is a FIFO queue, which has the following implications:"
  echo "1. Messages are processed in strict order"
  echo "2. Exactly-once processing is possible"
  echo "3. Message deduplication may be enabled (using message body or MessageDeduplicationId)"
  echo "4. Messages must have a MessageGroupId"
  echo "5. Throughput is limited to 300 transactions per second per API action"
fi

# 8. Perform a test receive to check message format
echo -e "\n========== MESSAGE SAMPLE =========="
echo "Attempting to receive a sample message (non-destructive peek)..."
if [ -n "$SSO_PROFILE" ]; then
  aws "$SSO_PROFILE" sqs receive-message \
    --queue-url $QUEUE_URL \
    --attribute-names All \
    --message-attribute-names All \
    --max-number-of-messages 1 \
    --visibility-timeout 5 \
    --wait-time-seconds 1
else
  aws sqs receive-message \
    --queue-url $QUEUE_URL \
    --attribute-names All \
    --message-attribute-names All \
    --max-number-of-messages 1 \
    --visibility-timeout 5 \
    --wait-time-seconds 1
fi

echo -e "\n========== QUEUE DIAGNOSTIC SUMMARY =========="
echo "Queue: $QUEUE_NAME"
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo "Run at: $(date)"
echo ""
echo "To send a test message to this queue:"
if [ -n "$SSO_PROFILE" ]; then
  echo "aws $SSO_PROFILE sqs send-message --queue-url $QUEUE_URL --message-body '{\"test\":\"message\"}' --message-group-id test"
else
  echo "aws sqs send-message --queue-url $QUEUE_URL --message-body '{\"test\":\"message\"}' --message-group-id test"
fi
echo ""
echo "To purge all messages from this queue (USE WITH CAUTION):"
if [ -n "$SSO_PROFILE" ]; then
  echo "aws $SSO_PROFILE sqs purge-queue --queue-url $QUEUE_URL"
else
  echo "aws sqs purge-queue --queue-url $QUEUE_URL"
fi
echo ""
echo "To monitor this queue in real-time:"
echo "python listen_to_queue.py"
echo ""
echo "==================================================="