import argparse
import json
import os

from .server import run, load_data


def main():
    parser = argparse.ArgumentParser(
        prog="query-server",
        description="Serves queries from text",
    )
    parser.add_argument(
        "-d",
        "--data",
        type=str,
        help="Specify a data file",
    )
    parser.add_argument(
        "-o",
        "--outputs",
        type=str,
        help="Specify an outputs directory",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=float,
        default=0.5,
        help="Specify a lower confidence limit",
    )
    args = parser.parse_args()

    if not os.path.exists(args.data):
        print(f"File '{args.data}' does not seem to exist")
        return

    if not os.path.exists(args.outputs):
        print(f"Directory '{args.outputs}' does not seem to exist")
        return

    import faulthandler

    faulthandler.enable()

    run(args.data, args.outputs, args.limit)


# Force download of the model
def models():
    import spacy
    from sentence_transformers import SentenceTransformer

    _ = spacy.cli.download("en_core_web_sm")
    _model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
