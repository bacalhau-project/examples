- go to job-container
- Build updated container: `docker buildx build --push --no-cache --platform linux/amd64,linux/arm/v7,linux/arm64/v8 --no-cache -t docker.io/bacalhauproject/log-processor:v0.1 .`
  - Make sure to purge previous files for building (can cause key errors): `docker system prune -a`

- Go to `terraform` folder
- Log in to google cloud with `gcloud auth login`
- Make a copy of .env.json.example and rename it to .env.json
- Change the fields to make sense. At a minimum, you will need unique names for:
  - project_id
  - tailscale_key (go here to provision a tailscale_key - https://login.tailscale.com/admin/settings/keys - it should be "Reusable", "Expiration of 90 days", "Ephemeral" and have a tag of something meaningful to you.)
  - app_name
  - username
  - app_tag
- Run `terraform plan -out=tf.out -var-file=.env.json`
- If there are no errors, run `terraform apply tf.out`

You now have 4 a four node cluster.

-------

- API_HOST doesn't output public tag
- Show everything as a flag during `ps` - could leak