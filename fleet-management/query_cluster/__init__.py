import argparse

from . import config, task


def main():
    parser = argparse.ArgumentParser(
        prog="query-cluster",
        description="Bacalhau Distributed Cluster Management Query",
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
        help="Specify what nodes to run the query on (defaults to all)",
    )
    parser.add_argument(
        "-p", "--print", action="store_true", help="Print output to stdout"
    )
    parser.add_argument("query", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    cfg = config.load(args.config)
    task.run(cfg, args)
