import asyncio
import logging
import random
import time
import uuid

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

all_statuses = {}
task_total = 100

console = Console()

table_update_event = asyncio.Event()
table_update_running = False

events_to_progress = []

max_time = 5  # Changed to 5 seconds

logging.basicConfig(level=logging.INFO)


class InstanceStatus:
    def __init__(self, region, zone):
        # Generate a unique ID for each instance - maximum 6 characters
        self.id = f"{region}-{zone}-{uuid.uuid4()}"[:6]
        self.region = region
        self.zone = zone
        self.status = "Initializing"
        self.detailed_status = "Initializing"
        self.elapsed_time = 0
        self.instance_id = None
        self.public_ip = None
        self.private_ip = None
        self.vpc_id = None

    def combined_status(self):
        return f"{self.status} ({self.detailed_status})"


def make_progress_table():
    table = Table(show_header=True, header_style="bold magenta", show_lines=False)
    table.add_column("ID", width=8, style="cyan", no_wrap=True)
    table.add_column("Region", width=8, style="green", no_wrap=True)
    table.add_column("Zone", width=8, style="green", no_wrap=True)
    table.add_column("Status", width=15, style="yellow", no_wrap=True)
    table.add_column("Elapsed", width=8, justify="right", style="magenta", no_wrap=True)
    table.add_column("Instance ID", width=15, style="blue", no_wrap=True)
    table.add_column("Public IP", width=15, style="blue", no_wrap=True)
    table.add_column("Private IP", width=15, style="blue", no_wrap=True)

    sorted_statuses = sorted(all_statuses.values(), key=lambda x: (x.region, x.zone))
    for status in sorted_statuses:
        table.add_row(
            status.id[:8],
            status.region[:8],
            status.zone[:8],
            status.combined_status()[:15],
            f"{status.elapsed_time:.1f}s",
            (status.instance_id or "")[:15],
            (status.public_ip or "")[:15],
            (status.private_ip or "")[:15],
        )
    return table


def create_layout(progress, table):
    layout = Layout()
    progress_panel = Panel(
        progress,
        title="Progress",
        border_style="green",
        padding=(1, 1),
    )
    layout.split(
        Layout(progress_panel, size=5),
        Layout(table),
    )
    return layout


async def simulate_instance_creation(status, queue, progress_task):
    """Simulates the creation of a single instance."""
    for _ in range(10):  # 10 steps to simulate different stages
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Random delay between steps
        status.detailed_status = random.choice(
            ["Pending", "Provisioning", "Initializing", "Configuring"]
        )
        status.elapsed_time = time.time() - start_time
        await queue.put(status)  # Put the updated status into the queue
    status.status = "Running"
    await queue.put(status)
    progress_task.update(
        progress_task.id, advance=1
    )  # Update progress bar for each instance


async def update_table(live):
    global table_update_running, events_to_progress, all_statuses, console
    if table_update_running:
        logging.debug("Table update already running. Exiting.")
        return

    logging.debug("Starting table update.")

    try:
        table_update_running = True
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("[progress.completed]{task.completed} of {task.total}"),
            TextColumn("[progress.elapsed]{task.elapsed:>3.0f}s"),
            expand=True,
        )
        task = progress.add_task("Creating Instances", total=task_total)

        while not table_update_event.is_set() or events_to_progress:
            while events_to_progress:
                event = events_to_progress.pop(0)
                all_statuses[event.id] = event
                progress.update(task, completed=len(all_statuses))

            table = make_progress_table()
            layout = create_layout(progress, table)
            live.update(layout)

            await asyncio.sleep(0.05)  # Reduce sleep time for more frequent updates

    except Exception as e:
        logging.error(f"Error in update_table: {str(e)}")
    finally:
        table_update_running = False
        logging.debug("Table update finished.")


async def main():
    global events_to_progress, all_statuses

    start_time = time.time()
    end_time = start_time + 4  # Set to 4 seconds

    statuses_to_create = [
        InstanceStatus(str(random.randint(1, 100)), str(random.randint(1, 1000)))
        for _ in range(task_total)
    ]

    with Live(console=console, refresh_per_second=20) as live:
        update_table_task = asyncio.create_task(update_table(live))

        # Distribute status creation over 4 seconds
        for i in range(task_total):
            events_to_progress.append(statuses_to_create[i])
            if (i + 1) % 10 == 0:
                await asyncio.sleep(0.4)

        # Ensure all statuses are processed
        all_statuses.update({status.id: status for status in statuses_to_create})

        # If we finished early, wait until 4 seconds have passed
        time_elapsed = time.time() - start_time
        if time_elapsed < 4:
            await asyncio.sleep(4 - time_elapsed)

        table_update_event.set()
        await update_table_task

    # Print the final table outside of the Live context
    final_table = make_progress_table()
    console.print(final_table)


if __name__ == "__main__":
    asyncio.run(main())
