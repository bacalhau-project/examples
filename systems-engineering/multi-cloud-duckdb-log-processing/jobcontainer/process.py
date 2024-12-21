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


def get_storage_client(provider, storage_lib):
    try:
        if provider not in ["GCP", "AWS", "AZURE", "OCI"]:
            raise ValueError(f"Unsupported provider: {provider}")

        if not storage_lib:
            raise ValueError(f"storage_lib not found in NODE_INFO for provider {provider}")

        if provider == "GCP":
            return storage.Client()
        elif provider == "AWS":
            return boto3.client('s3')
        elif provider == "AZURE":
            conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
            if not conn_str:
                raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
            return BlobServiceClient.from_connection_string(conn_str)
        elif provider == "OCI":
            try:
                config = oci.config.from_file()
                return oci.object_storage.ObjectStorageClient(config)
            except Exception as e:
                raise ValueError(f"Failed to initialize OCI client: {str(e)}")
    except ImportError:
        raise ImportError(f"Required library '{storage_lib}' not installed for provider {provider}")
    except Exception as e:
        raise RuntimeError(f"Failed to initialize storage client for {provider}: {str(e)}")


def get_node_info():
    info = {}
    try:
        with open("/etc/NODE_INFO") as f:
            for line in f:
                if "=" not in line:
                    continue
                key, value = line.strip().split("=", 1)
                info[key.strip()] = value.strip()

        required_fields = ["provider", "storage_lib", "STORAGE_BUCKET"]
        missing_fields = [field for field in required_fields if field not in info]
        if missing_fields:
            raise ValueError(f"Missing required fields in NODE_INFO: {', '.join(missing_fields)}")

        return info
    except FileNotFoundError:
        raise RuntimeError("NODE_INFO file not found")
    except Exception as e:
        raise RuntimeError(f"Error reading NODE_INFO: {str(e)}")


def upload_to_provider_bucket(client, provider, node_info, output_file_name, result_json):
    bucket = node_info.get("STORAGE_BUCKET")
    if not bucket:
        raise ValueError("STORAGE_BUCKET not found in NODE_INFO")

    try:
        if provider == "GCP":
            bucket_obj = client.get_bucket(bucket)
            blob = bucket_obj.blob(output_file_name)
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
                temp.write(result_json)
                temp.close()
                blob.upload_from_filename(temp.name)
                os.remove(temp.name)
        elif provider == "AWS":
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
                temp.write(result_json)
                temp.close()
                client.upload_file(temp.name, bucket, output_file_name)
                os.remove(temp.name)
        elif provider == "AZURE":
            container_name = bucket.split("/")[-1]
            blob_client = client.get_blob_client(container=container_name, blob=output_file_name)
            blob_client.upload_blob(result_json, overwrite=True)
        elif provider == "OCI":
            namespace = os.environ.get("OCI_NAMESPACE")
            if not namespace:
                raise ValueError("OCI_NAMESPACE environment variable not set")
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
                temp.write(result_json)
                temp.close()
                with open(temp.name, "rb") as f:
                    client.put_object(namespace, bucket, output_file_name, f)
                os.remove(temp.name)
    except Exception as e:
        raise RuntimeError(f"Failed to upload to {provider} bucket: {str(e)}")


def upload_to_gcp_global_bucket(result_json, output_file_name):
    try:
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
    except Exception as e:
        raise RuntimeError(f"Failed to upload to central GCP bucket: {str(e)}")


def main(input_file, query, output_directory):
    try:
        # Get node info and validate provider
        node_info = get_node_info()
        provider = node_info.get("provider", "").upper()
        storage_lib = node_info.get("storage_lib")

        if not provider:
            raise ValueError("provider not found in NODE_INFO")

        # Initialize storage client
        client = get_storage_client(provider, storage_lib)

        # Set up DuckDB connection
        con = duckdb.connect(database=":memory:", read_only=False)
        con.execute("SET order_by_non_integer_literal=true")

        # Handle gzipped files
        usingTempFile = False
        if input_file.endswith(".gz"):
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as temp:
                os.system(f"gunzip -c {input_file} > {temp.name}")
                input_file = temp.name
                usingTempFile = True

        # Create and populate table
        con.execute("""
            CREATE TABLE IF NOT EXISTS log_data (
                id VARCHAR,
                "@timestamp" VARCHAR,
                "@version" VARCHAR,
                message VARCHAR
            )
        """)

        con.execute(
            "INSERT INTO log_data SELECT * FROM read_json(?, "
            "auto_detect=true,"
            f"columns={json.dumps({'id': 'varchar', '@timestamp': 'varchar', '@version': 'varchar', 'message': 'varchar'})})",
            [input_file],
        )

        # Execute query and format results
        result = con.execute(query).fetchdf()
        result_json = result.to_json(orient="records")

        # Generate output filename with provider info
        output_file_name = f"{node_info[f'{provider.lower()}.name']}-{datetime.now().strftime('%Y%m%d%H%M')}.json"

        try:
            # Upload to provider-specific bucket
            upload_to_provider_bucket(client, provider, node_info, output_file_name, result_json)
            print(f"Uploaded to {provider} bucket")

            # Upload to central GCP bucket
            upload_to_gcp_global_bucket(result_json, output_file_name)
            print("Uploaded to GCP global bucket")

            # Write local copy if requested
            if output_directory:
                os.makedirs(output_directory, exist_ok=True)
                local_path = f"{output_directory}/{output_file_name}"
                with open(local_path, "w") as outfile:
                    outfile.write(result_json)
                print(f"Local file written to {local_path}")

        except Exception as e:
            print(f"Error uploading results: {str(e)}")
            raise

    except Exception as e:
        print(f"Error processing log data: {str(e)}")
        raise
    finally:
        if usingTempFile and os.path.exists(input_file):
            os.remove(input_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process log data")
    parser.add_argument("input_file", help="Path to the input log file")
    parser.add_argument("query", help="DuckDB query to execute")
    parser.add_argument("--output_dir", default="/outputs", help="Directory to save the output JSON file")

    args = parser.parse_args()
    main(args.input_file, args.query, args.output_dir)
