# Multi-Region Bacalhau Nodes with Managed Instance Group

Set the project ID as an environment variable:
```bash
GCP_PROJECT_ID=bacalhau-miscellaneous
```

Create a GCS bucket to store the lock file:
```bash
GCS_BUCKET_NAME=multi-region-lock-bucket
gcloud storage buckets create gs://$GCS_BUCKET_NAME
```

Then create a service account and grant it permissions to the bucket

```bash
SERVICE_ACCOUNT_NAME=multi-region-bacalhau-sa
gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" --display-name "${SERVICE_ACCOUNT_NAME}"
```

Grant the service account permissions to the $GCS_BUCKET_NAME

```bash
gcloud projects add-iam-policy-binding ${GCP_PROJECT_ID} \
  --member serviceAccount:${SERVICE_ACCOUNT_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/storage.objectAdmin
```

Create a key for the service account and download it to your local machine

```bash
gcloud iam service-accounts keys create "${SERVICE_ACCOUNT_NAME}.json" \
  --iam-account "${SERVICE_ACCOUNT_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
```

Set the environment variable for the service account key file
```bash
export GOOGLE_APPLICATION_CREDENTIALS="${SERVICE_ACCOUNT_NAME}.json"
```

Now we're going to use the python script to first, create a lock file, and then download and run the bacalhau script to start the service.

```bash
python3 multi-region-bacalhau.py --project_id $GCP_PROJECT_ID --bucket_name $GCS_BUCKET_NAME --service_account $SERVICE_ACCOUNT_NAME
```

On each VM:
* Get the service account credentials
* See if the secret exists and is not null
* If the secret is null, see if the lock file is present
* If the lock file is present, wait for 30 seconds and try again
* If the lock file is not present, set the lock file and start the server from scratch
* If the secret is not null, start the server from the secret