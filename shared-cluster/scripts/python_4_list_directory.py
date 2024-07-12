import os
from datetime import datetime

import humanize
from rich.console import Console
from rich.table import Table


def list_azureshare_directory(directory):
    """
    Print a pretty tree of the azureshare directory with file details.
    """
    max_name_length = 0
    all_entries = []

    def collect_entries(dir_path, prefix=""):
        nonlocal max_name_length
        entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            full_name = f"{prefix}{'└── ' if is_last else '├── '}{entry.name}"
            if entry.is_file():
                size = humanize.naturalsize(entry.stat().st_size, gnu=True)
                date = datetime.fromtimestamp(entry.stat().st_mtime).isoformat()
                all_entries.append((full_name, size, date))
                max_name_length = max(max_name_length, len(full_name))
            if entry.is_dir():
                full_name += "/"
                all_entries.append((full_name, "", ""))
                max_name_length = max(max_name_length, len(full_name))
                collect_entries(entry.path, prefix + ("    " if is_last else "│   "))

    collect_entries(directory)

    max_size_length = max(len(entry[1]) for entry in all_entries)
    max_date_length = max(len(entry[2]) for entry in all_entries)
    required_width = max_name_length + max_size_length + max_date_length + 4

    console = Console(width=required_width)
    table = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    table.add_column("Name", style="bold", no_wrap=True)
    table.add_column("Size", style="bold", justify="right")
    table.add_column("Date", style="bold")

    for entry in all_entries:
        table.add_row(*entry)

    console.print(table)


def main():
    directory = os.environ.get("DIRECTORY", "/azureshare")
    list_azureshare_directory(directory)


if __name__ == "__main__":
    main()
