import argparse
from . import config, client


def main():
    parser = argparse.ArgumentParser(
        prog="llmclient",
        description="LLM Client",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=argparse.FileType("r"),
        default="config.yaml",
        help="Specify a config file, default: config.yaml",
    )

    args = parser.parse_args()

    cfg = config.load(args.config)
    client.run(cfg)
