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
import time

import boto3
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        console.print(f"[bold red]Error loading config.yaml: {e}[/bold red]")
        return {}


def create_sqs_client(config):
    # First try using the default credential provider chain (env vars, IAM role, SSO, etc.)
    try:
        console.print(
            "[yellow]Attempting to use AWS SSO or default credentials...[/yellow]"
        )
        return boto3.client("sqs", region_name=config["region"])
    except Exception as e:
        console.print(f"[bold red]Could not use default credentials: {e}[/bold red]")
        console.print(
            "[yellow]Falling back to credentials from config file...[/yellow]"
        )
        # Fall back to config credentials
        return boto3.client(
            "sqs",
            region_name=config["region"],
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
        )


def check_queue_compatibility(queue_url, sqs_client):
    """Check if our application configuration is compatible with the queue settings"""

    try:
        # Get queue attributes
        response = sqs_client.get_queue_attributes(
            QueueUrl=queue_url, AttributeNames=["All"]
        )

        attributes = response.get("Attributes", {})

        # Extract key settings
        is_fifo = attributes.get("FifoQueue", "false") == "true"
        content_dedup = attributes.get("ContentBasedDeduplication", "false") == "true"
        visibility_timeout = int(attributes.get("VisibilityTimeout", "30"))
        message_retention = int(attributes.get("MessageRetentionPeriod", "345600"))
        delay_seconds = int(attributes.get("DelaySeconds", "0"))

        # Print queue settings
        table = Table(title="Queue Settings")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Impact", style="yellow")

        table.add_row(
            "FIFO Queue",
            "Yes" if is_fifo else "No",
            "FIFO queues maintain strict order and require MessageGroupId",
        )

        table.add_row(
            "Content-Based Deduplication",
            "Enabled" if content_dedup else "Disabled",
            "When enabled, identical messages within 5 minutes are treated as duplicates",
        )

        table.add_row(
            "Visibility Timeout",
            f"{visibility_timeout} seconds",
            "How long messages are hidden after being received",
        )

        table.add_row(
            "Message Retention",
            f"{message_retention} seconds ({message_retention / 86400:.1f} days)",
            "How long messages are kept if not deleted",
        )

        table.add_row(
            "Delay Seconds",
            f"{delay_seconds} seconds",
            "Delay before messages become visible after being sent",
        )

        console.print(table)

        # Analyze potential issues based on settings
        issues = []

        if is_fifo:
            # Check our code for MessageGroupId
            with open("messages_mock.go", "r") as f:
                code = f.read()
                if "MessageGroupId" not in code:
                    issues.append(
                        "The FIFO queue requires MessageGroupId, but it may not be set in our code"
                    )

            # Check if deduplication is enabled
            if content_dedup:
                issues.append(
                    "Content-based deduplication is enabled - messages with identical bodies will be deduplicated within 5 minutes"
                )

        if visibility_timeout > 30:
            issues.append(
                f"Visibility timeout is {visibility_timeout} seconds - received messages won't be visible to other consumers during this time"
            )

        # Print analysis
        if issues:
            console.print(
                Panel(
                    "\n".join([f"• {issue}" for issue in issues]),
                    title="Potential Issues",
                    border_style="red",
                )
            )
        else:
            console.print(
                Panel(
                    "No obvious compatibility issues detected",
                    title="Analysis",
                    border_style="green",
                )
            )

        # Print recommendations
        recommendations = []

        if is_fifo:
            recommendations.append(
                "For FIFO queues, ensure every message has a unique MessageDeduplicationId (unless content deduplication is enabled)"
            )
            recommendations.append(
                "Messages with the same MessageGroupId are processed in strict order"
            )

        if visibility_timeout > 30:
            recommendations.append(
                f"Consider reducing the visibility timeout ({visibility_timeout}s) if you want messages to return to the queue faster"
            )

        recommendations.append(
            "If messages aren't showing up in monitoring tools, they might be being consumed immediately"
        )
        recommendations.append(
            "Use AWS Console's 'Send and receive messages' feature to manually test the queue"
        )

        console.print(
            Panel(
                "\n".join([f"• {rec}" for rec in recommendations]),
                title="Recommendations",
                border_style="cyan",
            )
        )

        return True

    except Exception as e:
        console.print(f"[bold red]Error checking queue settings: {e}[/bold red]")
        return False


def send_test_message(queue_url, sqs_client):
    """Send a test message to the queue and return the message ID"""
    try:
        # For FIFO queues
        dedup_id = f"test-{int(time.time())}"
        group_id = "test-group"

        msg_body = json.dumps(
            {
                "test": True,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": "Test message from diagnostic script",
            }
        )

        if queue_url.endswith(".fifo"):
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=msg_body,
                MessageGroupId=group_id,
                MessageDeduplicationId=dedup_id,
            )
        else:
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=msg_body,
            )

        message_id = response.get("MessageId")
        console.print(
            f"[green]✓ Test message sent successfully! Message ID: {message_id}[/green]"
        )
        return message_id
    except Exception as e:
        console.print(f"[bold red]Error sending test message: {e}[/bold red]")
        return None


def receive_test_message(queue_url, sqs_client, message_id=None):
    """Receive and verify a test message from the queue"""
    try:
        console.print("\n[yellow]Attempting to receive message from queue...[/yellow]")
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )

        if "Messages" in response and response["Messages"]:
            msg = response["Messages"][0]
            received_id = msg.get("MessageId")

            # Verify if this is our test message
            if message_id and received_id == message_id:
                console.print(
                    "[green]✓ Successfully received our test message![/green]"
                )
            else:
                console.print(
                    "[yellow]Received a message (but not our test message)[/yellow]"
                )

            # Print message details
            console.print(
                Panel(msg["Body"], title="Message Body", border_style="green")
            )

            # Delete the message since we've processed it
            sqs_client.delete_message(
                QueueUrl=queue_url, ReceiptHandle=msg["ReceiptHandle"]
            )
            console.print("[green]✓ Message deleted from queue[/green]")

            return True
        else:
            console.print("[yellow]No messages available in the queue[/yellow]")
            return False
    except Exception as e:
        console.print(f"[bold red]Error receiving message: {e}[/bold red]")
        return False


def main():
    console.print(Panel("FIFO Queue Configuration Checker", style="bold blue"))

    # Load configuration
    config = load_config()
    if not config:
        return

    queue_url = config.get("queue_url")
    if not queue_url:
        console.print("[bold red]Queue URL not found in config.yaml[/bold red]")
        return

    console.print(f"Queue URL: [green]{queue_url}[/green]")

    # Create SQS client
    try:
        sqs_client = create_sqs_client(config)
    except Exception as e:
        console.print(f"[bold red]Failed to create SQS client: {e}[/bold red]")
        return

    # Check queue settings
    if not check_queue_compatibility(queue_url, sqs_client):
        return

    # Check for message group IDs in our code
    try:
        with open("messages.go", "r") as f:
            code = f.read()
            if "MessageGroupId" in code:
                console.print("[green]✓ MessageGroupId is set in the code[/green]")
            else:
                console.print(
                    "[bold yellow]⚠ MessageGroupId might not be set - required for FIFO queues[/bold yellow]"
                )
    except Exception as e:
        console.print(f"[yellow]Could not check code for MessageGroupId: {e}[/yellow]")

    # Send test message
    console.print("\n[bold]Sending test message to queue...[/bold]")
    message_id = send_test_message(queue_url, sqs_client)

    if message_id:
        # Wait a moment for the message to be available
        time.sleep(2)
        # Receive and verify the message
        receive_test_message(queue_url, sqs_client, message_id)


if __name__ == "__main__":
    main()
