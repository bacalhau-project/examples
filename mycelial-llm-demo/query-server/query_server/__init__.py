import argparse
import json
import os

from .server import run


def main():
    parser = argparse.ArgumentParser(
        prog="query-server",
        description="Serves queries from text",
    )
    parser.add_argument(
        "-d",
        "--data",
        type=argparse.FileType("r"),
        default="sampl.json",
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

    if not os.path.exists(args.outputs):
        print(f"Directory '{args.outputs}' does not seem to exist")
        return

    import faulthandler

    faulthandler.enable()

    data = json.load(args.data)
    run(data, args.outputs, args.limit)


# Force download of the model
def models():
    import spacy
    from sentence_transformers import SentenceTransformer

    _ = spacy.cli.download("en_core_web_sm")
    _model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
