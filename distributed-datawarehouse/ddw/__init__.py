import argparse

from . import config, task


def main():
    parser = argparse.ArgumentParser(
        prog="ddw",
        description="Bacalhau Distributed Data Warehouse",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=argparse.FileType("r"),
        default="config.yaml",
        help="Specify a config file, default: config.yaml",
    )
    parser.add_argument(
        "-s",
        "--select",
        metavar="KEY=VALUE",
        help="Specify what nodes to run the query on",
    )
    parser.add_argument(
        "-a", "--all", action="store_true", help="Run on all matching nodes"
    )
    parser.add_argument(
        "-p", "--print", action="store_true", help="Print output to stdout"
    )
    parser.add_argument("query", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cfg = config.load(args.config)
    task.run(cfg, args)
