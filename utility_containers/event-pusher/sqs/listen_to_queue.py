#!/usr/bin/env uv run -s
# -*- coding: utf-8 -*-
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "boto3",
#     "botocore",
#     "pyyaml",
#     "rich",
# ]
# ///

import json
import os
import time
from datetime import datetime
from pathlib import Path

import boto3
import yaml
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


def load_config():
    # Look for config.yaml in the root directory
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def create_sqs_client(config):
    # First try using the default credential provider chain (env vars, IAM role, SSO, etc.)
    # This will use SSO if you've authenticated with 'aws sso login'
    try:
        print("Attempting to use AWS SSO or default credentials...")
        return boto3.client("sqs", region_name=config["region"])
    except Exception as e:
        print(f"Could not use default credentials: {e}")
        print("Falling back to credentials from config file...")
        # Fall back to credentials from config file
        return boto3.client(
            "sqs",
            region_name=config["region"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
        )


def get_queue_attributes(sqs_client, queue_url):
    response = sqs_client.get_queue_attributes(
        QueueUrl=queue_url,
        AttributeNames=[
            "ApproximateNumberOfMessages",
            "ApproximateNumberOfMessagesNotVisible",
        ],
    )
    return response["Attributes"]


def format_message(message):
    # Extract the message body
    body = message.get("Body", "")

    # Try to parse as JSON if it looks like JSON
    try:
        if body.strip().startswith("{") and body.strip().endswith("}"):
            parsed_body = json.loads(body)
            # If we have a structured message from our event-pusher, format it nicely
            if "vm_name" in parsed_body and "icon_name" in parsed_body:
                formatted_body = (
                    f"{parsed_body.get('vm_name')} | "
                    f"{parsed_body.get('icon_name')} | "
                    f"{parsed_body.get('color')} | "
                    f"{parsed_body.get('container_id')}"
                )
                body = formatted_body
    except:
        # If parsing fails, just use the raw body
        pass

    # Get the timestamp
    timestamp = message.get("Attributes", {}).get("SentTimestamp", "")
    if timestamp:
        timestamp = datetime.fromtimestamp(int(timestamp) / 1000).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # If there's a message timestamp in the body, use that instead
    try:
        if body.strip().startswith("{") and body.strip().endswith("}"):
            parsed_body = json.loads(body)
            if "timestamp" in parsed_body:
                return f"[{parsed_body['timestamp']}] {body}"
    except:
        pass

    return f"[{timestamp}] {body}"


def main():
    console = Console()
    config = load_config()
    sqs_client = create_sqs_client(config)
    queue_url = config["queue_url"]

    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="stats", size=5),
        Layout(name="messages"),
    )

    with Live(layout, refresh_per_second=1) as live:
        while True:
            # Update header
            layout["header"].update(Panel("SQS Queue Monitor", style="bold blue"))

            # Get queue statistics
            attrs = get_queue_attributes(sqs_client, queue_url)
            visible = int(attrs["ApproximateNumberOfMessages"])
            not_visible = int(attrs["ApproximateNumberOfMessagesNotVisible"])
            total = visible + not_visible

            # Create stats table
            stats_table = Table(show_header=False, box=None)
            stats_table.add_row("Visible Messages:", str(visible))
            stats_table.add_row("In-Flight Messages:", str(not_visible))
            stats_table.add_row("Total Messages:", str(total))
            layout["stats"].update(Panel(stats_table, title="Queue Statistics"))

            # Get and display messages
            new_messages = []
            try:
                response = sqs_client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    MessageAttributeNames=["All"],
                    AttributeNames=["All"],
                    VisibilityTimeout=30,  # Longer timeout to prevent re-receiving
                    WaitTimeSeconds=20,  # Longer wait to reduce API calls
                )

                if "Messages" in response:
                    for msg in response["Messages"]:
                        # Extract body and try to parse it as a message
                        body = msg.get("Body", "")

                        # Get message timestamp - either from message attributes or SQS timestamp
                        timestamp = msg.get("Attributes", {}).get("SentTimestamp", "")
                        if timestamp:
                            timestamp = datetime.fromtimestamp(
                                int(timestamp) / 1000
                            ).strftime("%Y-%m-%d %H:%M:%S.%f")

                        formatted_msg = f"[{timestamp}] {body}"
                        new_messages.append(formatted_msg)

                        # Delete the message after processing
                        try:
                            sqs_client.delete_message(
                                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
                            )
                        except Exception as e:
                            console.print(
                                f"[red]Error deleting message: {str(e)}[/red]"
                            )
            except Exception as e:
                new_messages = [f"Error receiving messages: {str(e)}"]

            # Create messages panel
            if new_messages:
                messages_text = "\n".join(new_messages)
                messages_text = f"[green]New messages received at {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}:[/green]\n{messages_text}"
            else:
                messages_text = "Waiting for new messages..."

            layout["messages"].update(Panel(messages_text, title="Recent Messages"))

            time.sleep(1)


if __name__ == "__main__":
    main()
