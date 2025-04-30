#!/usr/bin/env python3
"""
Utility script: Upload Parquet files from a local directory to AWS S3 or Azure Data Lake Storage Gen2.
"""
import argparse
import logging
import sys
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(
        description="Upload Parquet files to S3 or ADLS Gen2"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Local directory containing Parquet files"
    )
    parser.add_argument(
        "--bucket", required=True,
        help="Cloud storage bucket/container name"
    )
    parser.add_argument(
        "--prefix", default="",
        help="Key prefix or path under the bucket/container"
    )
    parser.add_argument(
        "--region", default=None,
        help="AWS region (only for S3 uploads)"
    )
    parser.add_argument(
        "--delete", action="store_true",
        help="Delete local files after successful upload"
    )
    return parser.parse_args()


def upload_to_s3(file_path, bucket, key, region):
    import boto3
    s3 = boto3.client("s3", region_name=region)
    s3.upload_file(str(file_path), bucket, key)


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    input_path = Path(args.input_dir)
    if not input_path.is_dir():
        logging.error(f"Input directory does not exist: {input_path}")
        sys.exit(1)

    for parquet_file in input_path.glob("*.parquet"):
        key = f"{args.prefix.rstrip('/')}/{parquet_file.name}" if args.prefix else parquet_file.name
        logging.info(f"Uploading {parquet_file} to {bucket}/{key}")
        try:
            upload_to_s3(parquet_file, args.bucket, key, args.region)
            logging.info(f"Successfully uploaded {parquet_file.name}")
            if args.delete:
                parquet_file.unlink()
                logging.info(f"Deleted local file: {parquet_file}")
        except Exception as e:
            logging.error(f"Failed to upload {parquet_file.name}: {e}", exc_info=True)
            sys.exit(1)

if __name__ == "__main__":
    main()
