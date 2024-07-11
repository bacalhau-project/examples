import asyncio
import os
import re
import sys
import time

import aiohttp
from aiofiles import open as aioopen
from aiohttp import ClientSession, ClientTimeout
from bs4 import BeautifulSoup
from rich.console import Console
from rich.live import Live
from rich.progress import Progress, TaskID
from rich.table import Table

# Maximum number of concurrent downloads
MAX_CONCURRENT_DOWNLOADS = 5

# Number of retry attempts
RETRY_ATTEMPTS = 3

# Directory to save downloaded files
DOWNLOAD_DIR = "/mnt/azureshare"

# Rich console for pretty printing
console = Console()

# Global progress tracking
progress = Progress()
overall_task = progress.add_task("[cyan]Overall Progress", total=0)
download_tasks = {}


def create_table() -> Table:
    """Create and return a table for displaying download progress."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Filename", style="dim", width=20)
    table.add_column("Status", justify="center")
    table.add_column("Progress", justify="right")
    table.add_column("Size", justify="right")
    table.add_column("Speed", justify="right")
    return table


async def get_file_urls(root_url: str, session: ClientSession) -> list:
    """Crawl the root URL and return a list of file URLs."""
    file_urls = []

    console.print(f"[yellow]Attempting to access {root_url}")

    try:
        async with session.get(root_url) as response:
            response.raise_for_status()
            html = await response.text()
            console.print(f"[green]Successfully retrieved HTML from {root_url}")
    except aiohttp.ClientResponseError as e:
        console.print(f"[bold red]Error accessing {root_url}: {e}")
        return file_urls
    except aiohttp.ClientError as e:
        console.print(f"[bold red]Network error accessing {root_url}: {e}")
        return file_urls

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=True)
    console.print(f"[blue]Found {len(links)} links on the page")

    for link in links:
        href = link["href"]
        if re.search(r"\.(pdf|jpg|jpeg|png|gif|mp3|mp4|zip|rar|h5)$", href, re.I):
            full_url = f"{root_url.rstrip('/')}/{href.lstrip('/')}"
            file_urls.append(full_url)
            console.print(f"[green]Found file: {full_url}")

    console.print(f"[yellow]Total files found: {len(file_urls)}")
    return file_urls


async def download_file(
    session: ClientSession, url: str, semaphore: asyncio.Semaphore, task_id: TaskID
):
    """Download a file from the given URL and save it to the DOWNLOAD_DIR."""
    filename = os.path.join(DOWNLOAD_DIR, url.split("/")[-1])
    attempt = 0
    success = False

    # Check if file already exists
    file_size = 0
    if os.path.exists(filename):
        file_size = os.path.getsize(filename)

    async with semaphore:
        try:
            # First, send a HEAD request to get the file size without downloading
            async with session.head(url) as head_response:
                head_response.raise_for_status()
                total_size = int(head_response.headers.get("content-length", 0))

            # If file exists and sizes match, mark as complete
            if file_size == total_size:
                progress.update(
                    task_id,
                    total=total_size,
                    completed=total_size,
                    status="[bold green]Complete (Already exists)",
                    size=f"{file_size / 1024 / 1024:.2f} MB",
                )
                return

            while attempt < RETRY_ATTEMPTS and not success:
                try:
                    start_time = time.time()
                    headers = {"Range": f"bytes={file_size}-"} if file_size > 0 else {}
                    async with session.get(url, headers=headers) as response:
                        response.raise_for_status()
                        if file_size == 0:
                            total_size = int(response.headers.get("content-length", 0))
                        progress.update(task_id, total=total_size)
                        progress.update(task_id, description=f"[bold blue]{filename}")
                        downloaded_size = file_size
                        mode = "ab" if file_size > 0 else "wb"
                        async with aioopen(filename, mode) as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                downloaded_size += len(chunk)
                                elapsed_time = time.time() - start_time
                                speed = (
                                    (downloaded_size - file_size) / elapsed_time
                                    if elapsed_time > 0
                                    else 0
                                )
                                progress.update(
                                    task_id,
                                    completed=downloaded_size,
                                    description=f"[bold blue]{filename}",
                                    status="[green]Downloading",
                                    size=f"{downloaded_size / 1024 / 1024:.2f} MB",
                                    speed=f"{speed / 1024 / 1024:.2f} MB/s",
                                )
                    progress.update(task_id, status="[bold green]Complete")
                    success = True
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    attempt += 1
                    progress.update(
                        task_id, status=f"[bold red]Retry {attempt}/{RETRY_ATTEMPTS}"
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        except Exception as e:
            console.print(f"[bold red]Error downloading {url}: {str(e)}")
            progress.update(task_id, status="[bold red]Failed")

    if not success:
        progress.update(task_id, status="[bold red]Failed")


async def download_all_files(urls):
    """Download all files concurrently."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    table = create_table()

    progress.update(overall_task, total=len(urls))

    timeout = ClientTimeout(total=3600)  # 1 hour timeout
    async with ClientSession(timeout=timeout) as session:
        with Live(table, refresh_per_second=4) as live:
            for url in urls:
                filename = url.split("/")[-1]
                task_id = progress.add_task(
                    f"[cyan]{filename}", filename=filename, status="Pending", total=0
                )
                download_tasks[url] = task_id
                table.add_row(filename, "Pending", "0%", "0 MB", "0 MB/s")

            tasks = [
                download_file(session, url, semaphore, task_id)
                for url, task_id in download_tasks.items()
            ]

            while tasks:
                done, tasks = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    await task

                # Rebuild the table, putting active downloads at the top
                new_table = create_table()
                active_downloads = []
                other_rows = []

                for task in progress.tasks:
                    if isinstance(
                        task.description, str
                    ) and task.description.startswith("[cyan]"):
                        filename = task.description.strip("[cyan]")
                        status = task.fields.get("status", "")
                        progress_str = f"{task.percentage:.0f}%"
                        size = task.fields.get("size", "0 MB")
                        speed = task.fields.get("speed", "0 MB/s")

                        row_data = (filename, status, progress_str, size, speed)
                        if "Downloading" in status:
                            active_downloads.append(row_data)
                        else:
                            other_rows.append(row_data)

                for row in active_downloads:
                    new_table.add_row(*row)
                for row in other_rows:
                    new_table.add_row(*row)

                table = new_table
                live.update(table)

    console.print(progress)


if __name__ == "__main__":
    # Ensure the download directory exists
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Run the async download function
    async def main():
        if len(sys.argv) < 2:
            console.print(
                "[bold red]Error: Please provide the root URL as a command-line argument."
            )
            sys.exit(1)

        root_url = sys.argv[1]

        console.print(f"[bold green]Starting crawler for root URL: {root_url}")

        timeout = ClientTimeout(total=3600)  # 1 hour timeout
        async with ClientSession(timeout=timeout) as session:
            file_urls = await get_file_urls(root_url, session)
            if not file_urls:
                console.print("[bold red]No files found. Printing HTML content:")
                async with session.get(root_url) as response:
                    html = await response.text()
                    console.print(html)
            else:
                console.print(f"[bold blue]Found {len(file_urls)} files to download.")
                await download_all_files(file_urls)

        console.print("[bold green]Process completed.")

    asyncio.run(main())
