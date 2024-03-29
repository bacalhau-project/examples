```
Bash
gcloud compute firewall-rules create http-to-lb \
  --allow tcp:80 \
  --direction=INGRESS \
  --source-ranges=0.0.0.0/0 \
  --description="Allow incoming HTTP traffic on port 80"

gcloud compute instances add-tags hydra-lb --tags=hydra-lb
```
