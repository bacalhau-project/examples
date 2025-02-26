# AWS SSH Keys

This directory contains SSH key pairs for accessing AWS instances. These files are sensitive and should never be committed to version control.

## Required Keys

1. `BacalhauSpotInstancesKey.pem` - Main SSH key pair for accessing spot instances
   - Generated when running setup scripts
   - Must be kept private and secure
   - Should have permissions set to 400 (`chmod 400 BacalhauSpotInstancesKey.pem`)

## Security Notes

- Never commit these keys to git
- Keep backups in a secure location
- Rotate keys regularly
- Ensure proper file permissions
