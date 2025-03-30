import os
import json
import logging
from fastapi import FastAPI, HTTPException, Request
import boto3
import uvicorn
from collections import defaultdict
from typing import Dict, Optional
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# AWS SQS client setup with connection pooling
sqs = boto3.client(
    'sqs',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    config=boto3.session.Config(
        max_pool_connections=100,  # Key improvement: connection pooling
        connect_timeout=5,
        read_timeout=10
    )
)

QUEUE_URL = os.getenv('SQS_QUEUE_URL')

# Track latest submission time per hostname with thread safety
latest_submissions: Dict[str, int] = defaultdict(lambda: 0)
hostname_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)

def should_process_message(message_body: dict) -> bool:
    """
    Determine if a message should be processed based on its submission time and hostname.
    Returns True if the message should be processed, False if it should be filtered out.
    Thread-safe implementation using per-hostname locks.
    """
    hostname = message_body.get('hostname')
    job_submission_time = message_body.get('job_submission_time')
    job_id = message_body.get('job_id', 'unknown')
    
    if not hostname or job_submission_time is None:
        logger.warning(f"Message missing hostname or job_submission_time: {message_body}")
        return False
    
    with hostname_locks[hostname]:
        # Update latest submission time if this message is newer
        if job_submission_time > latest_submissions[hostname]:
            latest_submissions[hostname] = job_submission_time
            logger.info(f"Updated latest submission time for {hostname} with job {job_id} to {job_submission_time}")
            return True
        
        # If the submission time is the same as the latest submission time, process the message
        if job_submission_time == latest_submissions[hostname]:
            return True

        # Filter out messages from older submissions
        logger.debug(f"Filtering out message from {hostname} (job: {job_id}) with submission time {job_submission_time} (latest: {latest_submissions[hostname]})")
        return False

@app.post("/send")
async def send_message(request: Request):
    try:
        # Accept any JSON body
        message_body = await request.json()
        
        # Check if we should process this message
        if not should_process_message(message_body):
            return {"status": "filtered", "message": "Message filtered due to newer submission"}
        
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(message_body)
        )
        logger.info(f"Message sent successfully - ID: {response['MessageId']}")
        logger.debug(f"Message content: {message_body}")
        return {"message_id": response['MessageId']}
    except json.JSONDecodeError:
        logger.error("Invalid JSON received")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    logger.info(f"Starting SQS proxy for queue: {QUEUE_URL}")

    # Use Bacalhau port if available, otherwise default to 8080
    port = int(os.getenv('BACALHAU_PORT_http', '8080'))
    uvicorn.run("proxy:app", host="0.0.0.0", port=port)