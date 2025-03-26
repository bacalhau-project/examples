import os
import json
import logging
from fastapi import FastAPI, HTTPException, Request
import boto3
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger(__name__)

app = FastAPI()

# AWS SQS client setup
sqs = boto3.client(
    'sqs',
    region_name=os.getenv('AWS_REGION', 'us-east-1')
)

QUEUE_URL = os.getenv('SQS_QUEUE_URL')

@app.post("/send")
async def send_message(request: Request):
    try:
        # Accept any JSON body
        message_body = await request.json()
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
    uvicorn.run(app, host="0.0.0.0", port=port)