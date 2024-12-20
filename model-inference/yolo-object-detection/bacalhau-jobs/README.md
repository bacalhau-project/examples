The IP address of the requester node is 34.130.12.148
When connecting to the requester for the first time you will be prompted for a token, ask Forrest for the token
To run a job you need to use a template variable to provide the job spec with a password to connect to https://expanso.gcp.us-west2.gcp.aperturedata.io/status
The command to run a job is:
`bacalhau job run publish-small-model-person.yaml --template-vars "adb_password=<APERTURE_PASSWORD>"`

There is a job file that is fully templated, you can run it like this:
`bacalhau job run template-job-publish.yaml --template-vars "classes=<CLASS_LIST>,input_bucket=<BUCKET_NAME>,model_url=<MODEL_URL>,adb_password=<APERTURE_PASSWORD>"
