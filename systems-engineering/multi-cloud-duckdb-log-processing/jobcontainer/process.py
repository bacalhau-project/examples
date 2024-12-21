import json
import os
import tempfile
import argparse
from datetime import datetime
import duckdb
from google.cloud import storage
import boto3
from azure.storage.blob import BlobServiceClient
import oci


def get_storage_client(provider):
    if provider == "gcp":
        return storage.Client()
    elif provider == "aws":
        return boto3.client('s3')
    elif provider == "azure":
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not conn_str:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
        return BlobServiceClient.from_connection_string(conn_str)
    elif provider == "oracle":
        config = oci.config.from_file()
        return oci.object_storage.ObjectStorageClient(config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")


def get_node_info():
    info = {}
    try:
        with open("/etc/NODE_INFO") as f:
            for line in f:
                if "=" not in line:
                    continue
                key, value = line.strip().split("=", 1)
                info[key.strip()] = value.strip()
    except FileNotFoundError:
        raise RuntimeError("NODE_INFO file not found")
    return info


def upload_to_provider_bucket(client, provider, node_info, output_file_name, result_json):
    bucket = node_info.get("STORAGE_BUCKET")
    if not bucket:
        raise ValueError("STORAGE_BUCKET not found in NODE_INFO")

    if provider == "gcp":
        bucket_obj = client.get_bucket(bucket)
        blob = bucket_obj.blob(output_file_name)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write(result_json)
            temp.close()
            blob.upload_from_filename(temp.name)
            os.remove(temp.name)
    elif provider == "aws":
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write(result_json)
            temp.close()
            client.upload_file(temp.name, bucket, output_file_name)
            os.remove(temp.name)
    elif provider == "azure":
        container_name = bucket.split("/")[-1]
        blob_client = client.get_blob_client(container=container_name, blob=output_file_name)
        blob_client.upload_blob(result_json, overwrite=True)
    elif provider == "oracle":
        namespace = os.environ.get("OCI_NAMESPACE")
        if not namespace:
            raise ValueError("OCI_NAMESPACE environment variable not set")
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
            temp.write(result_json)
            temp.close()
            with open(temp.name, "rb") as f:
                client.put_object(namespace, bucket, output_file_name, f)
            os.remove(temp.name)


def upload_to_gcp_global_bucket(result_json, output_file_name):
    client = storage.Client()
    global_bucket_name = os.environ.get("CENTRAL_LOGGING_BUCKET")
    if not global_bucket_name:
        raise ValueError("CENTRAL_LOGGING_BUCKET environment variable not set")

    bucket = client.get_bucket(global_bucket_name)
    blob = bucket.blob(output_file_name)
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
        temp.write(result_json)
        temp.close()
        blob.upload_from_filename(temp.name)
        os.remove(temp.name)


def main(input_file, query, output_directory):
    con = duckdb.connect(database=":memory:", read_only=False)

    usingTempFile = False
    if input_file.endswith(".gz"):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as temp:
            os.system(f"gunzip -c {input_file} > {temp.name}")
            input_file = temp.name
            usingTempFile = True

    con.execute(
        "CREATE TABLE log_data AS SELECT * FROM read_json(?, "
        "auto_detect=true,"
        f"columns={json.dumps({'id': 'varchar', '@timestamp': 'varchar', '@version': 'varchar', 'message': 'varchar'})})",
        [input_file],
    )

    result = con.execute(query).fetchdf()
    result_json = result.to_json(orient="records")

    node_info = get_node_info()
    provider = node_info.get("provider", "").lower()
    if not provider:
        raise ValueError("provider not found in NODE_INFO")
    output_file_name = f"{node_info[f'{provider}.name']}-{datetime.now().strftime('%Y%m%d%H%M')}.json"
    client = get_storage_client(provider)

    try:
        upload_to_provider_bucket(client, provider, node_info, output_file_name, result_json)
        print(f"Uploaded to {provider} bucket")

        upload_to_gcp_global_bucket(result_json, output_file_name)
        print("Uploaded to GCP global bucket")

        if output_directory:
            os.makedirs(output_directory, exist_ok=True)
            local_path = f"{output_directory}/{output_file_name}"
            with open(local_path, "w") as outfile:
                outfile.write(result_json)
            print(f"Local file written to {local_path}")

    except Exception as e:
        print(f"Error uploading results: {str(e)}")
        raise

    if usingTempFile:
        os.remove(input_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    parser.add_argument("query", help="DuckDB query to execute")
    parser.add_argument("--output_dir", default="/outputs", help="Directory to save the output JSON file")

    args = parser.parse_args()
    main(args.input_file, args.query, args.output_dir)
