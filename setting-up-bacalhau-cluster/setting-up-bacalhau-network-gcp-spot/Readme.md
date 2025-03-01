
### Remember to set default authorization variables:
```bash
export GCP_PROJECT_ID=expanso
export GOOGLE_APPLICATION_CREDENTIALS=/some/path/to/auth//expanso-auth-json.json
```
### Configure
Just provide ssh key, Bacalhau orchestrator URL(s) and token, to config.yaml (copy from config.yaml_example).

### Run
```bash
python -m venv .env
source ./env/source/activate
pip install -r requirements.txt

python deploy_spot.py --action list|create|destroy
```
