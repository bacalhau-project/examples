
### Remember to set default authorization variables:
```bash
export GCP_PROJECT_ID=expanso
export GOOGLE_APPLICATION_CREDENTIALS=/some/path/to/auth//expanso-auth-json.json
```

### Run
```bash
python -m venv .env
source ./env/source/activate
pip install -r requirements.txt

python deploy_spot.py --action list|create|destroy
```
