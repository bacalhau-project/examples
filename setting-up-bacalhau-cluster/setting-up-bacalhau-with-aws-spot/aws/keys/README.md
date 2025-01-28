# AWS SSH Keys

This directory contains SSH key pairs for accessing AWS instances. These files are sensitive and should never be committed to version control.

## Required Keys

1. `BacalhauScaleTestKey.pem` - Main SSH key pair for accessing spot instances
   - Generated when running setup scripts
   - Must be kept private and secure
   - Should have permissions set to 600 (`chmod 600 BacalhauScaleTestKey.pem`)

## Security Notes

- Never commit these keys to git
- Keep backups in a secure location
- Rotate keys regularly
- Ensure proper file permissions

## Setup

To create a new key pair:

1. Use AWS Console:
   ```bash
   aws ec2 create-key-pair --key-name BacalhauScaleTestKey --query 'KeyMaterial' --output text > BacalhauScaleTestKey.pem
   chmod 600 BacalhauScaleTestKey.pem
   ```

2. Update the key name in `aws/config/env.sh`
