import os
import boto3
import json
import logging
import requests
import traceback
import sys

from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get configurations from environment variables
opensearch_url = os.environ.get('OPENSEARCH_ENDPOINT')
dashboard_url = opensearch_url + '/_dashboards'
compute_role_arn = os.environ.get('COMPUTE_ROLE_ARN')


def get_secret():
    secrets_client = boto3.client('secretsmanager')
    response = secrets_client.get_secret_value(SecretId=os.environ.get('SECRET_ARN'))
    return HTTPBasicAuth('admin', response['SecretString'])


auth = get_secret()


def load_saved_objects():
    session = requests.Session()
    login_url = f"{dashboard_url}/auth/login"
    login_headers = {'Content-Type': 'application/json', 'osd-xsrf': 'true'}
    login_data = json.dumps({"username": auth.username, "password": auth.password})

    login_response = session.post(login_url, headers=login_headers, data=login_data)
    login_response.raise_for_status()
    logger.info(f"Successfully logged in: {login_response.json()}")

    url = f'{dashboard_url}/api/saved_objects/_import?overwrite=true'
    headers = {'osd-xsrf': 'true'}

    try:
        # Read the dashboard file
        with open('dashboard.ndjson', 'rb') as f:
            files = {'file': f}

            # Upload saved objects to OpenSearch Dashboard
            response = session.post(url, files=files, headers=headers)
            response.raise_for_status()  # Check for HTTP errors

            logger.info(f"Successfully loaded saved objects: {response.json()}")

    except FileNotFoundError:
        log_and_exit("Dashboard file 'dashboard.ndjson' not found.")
    except RequestException as e:
        log_and_exit("HTTP Request failed.", e)
    except Exception as e:
        log_and_exit("An unexpected error occurred.", e)


def update_role_mapping():
    url = f'{opensearch_url}/_plugins/_security/api/rolesmapping/all_access'
    headers = {'Content-Type': 'application/json'}

    try:
        # Fetch existing role mapping
        existing_mapping = requests.get(url, headers=headers, auth=auth)
        existing_mapping.raise_for_status()  # Check for HTTP errors

        existing_users = existing_mapping.json().get('all_access', {}).get('users', [])
        if not existing_users:
            logger.warning("Could not fetch existing users or none exist.")
            existing_users = []

        # Check if user already exists in role mapping
        if compute_role_arn in existing_users:
            logger.info("User %s already exists in the role mapping.", compute_role_arn)
            return

        # Update role mapping
        users = existing_users + [compute_role_arn]
        data = [
            {
                "op": "replace", "path": "/users", "value": users
            }
        ]

        response = requests.patch(url, data=json.dumps(data), headers=headers, auth=auth)
        response.raise_for_status()  # Check for HTTP errors

        logger.info(f"Successfully updated role mapping: {response.json()}")

    except RequestException as e:
        log_and_exit("HTTP Request failed.", e)
    except KeyError as e:
        log_and_exit("Unexpected response structure: Missing key.", e)
    except Exception as e:
        log_and_exit("An unexpected error occurred.", e)


def log_and_exit(error_message, exception=None):
    logger.error(error_message)
    if exception:
        logger.error(f"Exception details: {exception}")
    logger.error(traceback.format_exc())
    sys.exit(1)


def lambda_handler(event, context):
    if event.get('RequestType') == 'Delete':
        logger.info("Skipping dashboard initialization for Delete event.")
        return
    logger.info("Initializing dashboard with event: %s", event)
    load_saved_objects()
    update_role_mapping()
