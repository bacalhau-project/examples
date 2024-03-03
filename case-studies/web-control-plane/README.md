## Make sure following APIs are enabled
```
gcloud services enable apigateway.googleapis.com
gcloud services enable servicemanagement.googleapis.com
gcloud services enable servicecontrol.googleapis.com
```

Add the following role:
```
PROJECT_ID=hydra-415522
EMAIL_ADDRESS="aronchick@expanso.io"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member='user:aronchick@expanso.io' \
  --role='roles/owner'
```
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member='user:aronchick@expanso.io' \
  --role='roles/serviceconfig.editor'



## Creating a new instance from scratch for testing
```
PROJECT_ID=hydra-415522
ZONE=us-central1-a
INSTANCE_NAME=instance-$RANDOM
gcloud compute networks create global-network --project ${PROJECT_ID} --zone ${ZONE}

gcloud compute firewall-rules create ssh-and-http --network global-network --allow tcp:22,tcp:80,icmp

gcloud compute firewall-rules create default-allow-internal --network=global-network --action=allow --direction=ingress --source-ranges=10.0.0.0/8 --rules=all

gcloud compute instances create ${INSTANCE_NAME} \
    --project=${PROJECT_ID} \
    --zone=${ZONE} \
    --machine-type=e2-medium \
    --network-interface=network=global-network \
    --metadata=enable-oslogin=true \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append \
    --create-disk=auto-delete=yes,boot=yes,device-name=${INSTANCE_NAME},image=projects/ubuntu-os-cloud/global/images/ubuntu-2004-focal-v20240227,mode=rw,size=10,type=projects/${PROJECT_ID}/zones/${ZONE}/diskTypes/pd-balanced \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=goog-ec-src=vm_add-gcloud \
    --reservation-affinity=any

gcloud compute instances add-tags ${INSTANCENAME} --tags=allow-ssh,allow-bacalhau,default-allow-internal --zone ${ZONE}

PROJECT_ID=hydra-415522 \
INSTANCENAME=instance-3450 \
ZONE=us-central1-a \
INSTANCEIP=$(gcloud compute instances describe ${INSTANCENAME} --zone=${ZONE} --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

gcloud compute instances list --project=${PROJECT_ID} --zones=${ZONE}
```

```
rsync -av terraform/node_files/*.sh justiconsrunner@104.155.191.236:.
ssh justiconsrunner@104.155.191.236 "sudo ./install_gunicorn_services.sh"

rsync -av --exclude '\.*' --exclude "__*" client/ justiconsrunner@104.155.191.236:/home/justiconsrunner/justiconsapp
```


-----

LB Setup
```
gcloud compute addresses create justicons-lb-ip --global
gcloud compute addresses list
gcloud compute backend-services create justicons-backend-service --global --protocol HTTP --port-name http --timeout=60s --connection-draining-timeout=60s
gcloud compute backend-services add-backend justicons-backend-service --global --instance-group=justicons-group --instance-group-zone=us-central1-a
gcloud compute url-maps create justicons-url-map --default-service justicons-backend-service
gcloud compute url-maps add-path-matcher justicons-url-map --default-service justicons-backend-service --path-matcher-name pathmap --new-hosts="justicons.expanso.io"
gcloud compute target-http-proxies create justicons-http-proxy --url-map justicons-url-map
gcloud compute forwarding-rules create justicons-http-rule --address justicons-lb-ip --global --target-http-proxy justicons-http-proxy --ports 80
```

```
apt install -y nginx
```

```
gcloud compute networks create global-network \
    --subnet-mode=auto \
    --description="Global network for VM connectivity"

gcloud compute firewall-rules create allow-http-ssh-global \
    --direction=INGRESS \
    --priority=1000 \
    --network=global-network \
    --action=ALLOW \
    --rules=tcp:80,tcp:22 \
    --target-tags=hydra-lb \
    --source-ranges=0.0.0.0/0 \
    --description="Allow HTTP (port 80) and SSH (port 22) to VMs tagged 'hydra-lb'"

gcloud compute instances create global-lb \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --network-interface=network=global-network,stack-type=IPV4_ONLY \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=10GB \
    --boot-disk-type=pd-balanced \
    --metadata mount-hydra-lb=/olddisk,device-name=hydra-lb

tailscale up --authkey tskey-auth-kp8St33CNTRL-1rhvXc7poWaWcBEjzVaZaacZBtxY6s6qQ --hostname sales-demo-network-requestor
```
