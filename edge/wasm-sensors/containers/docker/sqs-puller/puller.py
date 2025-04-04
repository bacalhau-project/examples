import os
import json
import time
import boto3
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# AWS SQS client setup
sqs = boto3.client(
    'sqs',
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

QUEUE_URL = os.getenv('SQS_QUEUE_URL')
KEEP_FAILED_MESSAGES = os.getenv('KEEP_FAILED_MESSAGES', 'false').lower() == 'true'


def process_message(message):
    """Process a single message from SQS and log it.
    
    Args:
        message (dict): The SQS message to process
    """
    processed_data = {
        'message_id': message['MessageId'],
        'body': json.loads(message['Body']),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
    }
    logger.info(f"Message {message['MessageId']} processed successfully: {json.dumps(processed_data['body'])}")


def delete_message(message):
    """Delete a message from SQS.
    
    Args:
        message (dict): The SQS message to delete
    """
    sqs.delete_message(
        QueueUrl=QUEUE_URL,
        ReceiptHandle=message['ReceiptHandle']
    )


def main():
    logger.info(f"Starting SQS puller for queue: {QUEUE_URL}")
    logger.info(f"Keep failed messages: {KEEP_FAILED_MESSAGES}")

    while True:
        try:
            # Receive messages from SQS
            response = sqs.receive_message(
                QueueUrl=QUEUE_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20
            )

            if 'Messages' in response:
                for message in response['Messages']:
                    try:
                        # Process message
                        process_message(message)
                        # Always delete on success
                        delete_message(message)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)
                        if not KEEP_FAILED_MESSAGES:
                            delete_message(message)

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    main()
