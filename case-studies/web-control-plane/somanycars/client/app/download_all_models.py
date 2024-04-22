import argparse

import requests
import yaml
from tqdm import tqdm

if __name__ == "__main__":
    ArgumentParser = argparse.ArgumentParser
    parser = ArgumentParser("Download all models")
    parser.add_argument("--model_urls_path", type=str, default="./model_urls.yaml")
    args = parser.parse_args()

    model_urls = yaml.safe_load(open(args.model_urls_path, "r"))

    for url in model_urls.values():
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get("content-length", 0))
        block_size = 8192
        filename = url.split("/")[-1]
        filepath = f"./{filename}"

        with tqdm(total=total_size, unit="B", unit_scale=True) as progress_bar:
            with open(filepath, "wb") as file:
                for data in response.iter_content(block_size):
                    progress_bar.update(len(data))
                    file.write(data)

            if total_size != 0 and progress_bar.n != total_size:
                raise RuntimeError("Could not download file")
