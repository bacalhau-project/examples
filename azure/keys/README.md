# Azure Keys and Credentials

This directory should contain:

1. `azure_credentials.json` - Service Principal credentials file
2. `ssh_keys/` - Directory containing SSH keys for VM access
   - `id_rsa` - Private SSH key
   - `id_rsa.pub` - Public SSH key

To generate SSH keys:

```bash
mkdir -p ssh_keys
ssh-keygen -t rsa -b 4096 -C "bacalhau-azure-spot" -f ssh_keys/id_rsa
```

To create service principal credentials:

```bash
az ad sp create-for-rbac --sdk-auth > azure_credentials.json
```

**Important:** Never commit these files to version control!
