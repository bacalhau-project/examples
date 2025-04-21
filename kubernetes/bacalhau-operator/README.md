# Bacalhau Operator

This project aims to use Kubernetes as controlplane with [Bacalhau](https://docs.bacalhau.org/) as the orchestrator. This is a basic operator not meant for production use, yet.

## Prerequisites

To deploy this operator, you need to have access to a Kubernetes cluster. If you do not have access one, an easy solution is to install [Minikube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fmacos%2Farm64%2Fstable%2Fhomebrew) with the [docker driver](https://minikube.sigs.k8s.io/docs/drivers/docker/). 

Additionally, you will need to have access to a Bacalhau Network. If you do not already have one, you can easily create a new network using [Expanso Cloud](https://cloud.expanso.io/) free tier. If you are using Expanso Cloud, please see the section below about how to connect this K8s operator to it.

Moreover, if you are using a locally deployed Bacalhau orchestrator, you will need to make sure the K8S operator pods have network access to the Orchestrator's API endpoint.

## Deciding on the Bacalhau Network

### Expanso Cloud
If you are using Expanso Cloud, please take a note of the Endpoint provided to you when a network is provisioned; we will need that when we deploy the operator. For example, your Expanso Cloud Network endpoint might look like this: `https://g4hycm9u9ayp55.us1.cloud.expanso.io:1234`. Note: the port is mandatory.

Additionally, Expanso Cloud will provide you with an API KEY, please take a note of it, as we will need it as well for the operator deployment.

### Local Bacalhau Orchestrator
If you are using a local Bacalhau Operator, then you will need to make sure that the Operator Pods has network access to your locally deployed Bacalhau Operator. This really depends on your setup.

For example, if you are using MiniKube, you can utilize `http://host.minikube.internal:1234` as the endpoint for the Orchestrator. This leverages the internal `host.minikube.internal` minikube dns name that will route to your localhost.

Additionally, if you have deployed your Bacalhau Orchestrator with Authentication enabled, you will need to make note of the API Key, or Username/Password used.

### Default API Endpoint
Please note that the operator defaults the Bacalhau Endpoint to `http://bootstrap.production.bacalhau.org:1234/` which is a public testing network. We recommend using Expanso Cloud instead for easier experimentation.

## Installation of the Operator

In `bacalhau-operator.yaml`, change `API_Endpoint` to the Bacalhau Orchestrator Endpoint that you have chosen above. For example, if you chose Expanso Cloud, you will get an endpoint that looks like `https://g4hycm9u9ayp55.us1.cloud.expanso.io:1234`.

After updating the endpoint, run:
```bash
kubectl apply -f bacalhau-operator.yaml
```
This will create a bacalhau namespace, deploy the job controller and the needed CRDs.

Also, If your Bacalhau orchestrator has authentication enabled, you will need to update the API_Key secret, and restart the Operator deployment.

For example, lets say the API_KEY is `abc123abc123abc123`, run the command below to update the key (make sure to replace the value of the API_KEy with your own key):

```shell
kubectl create secret generic bacalhau-api-credentials \
  --namespace bacalhau-system \
  --from-literal=API_KEY=abc123abc123abc123 \
  --dry-run=client -o yaml | kubectl apply -f -
```

Then, redeploy the operator (make sure the Pods are running after the restart):
```shell
kubectl -n bacalhau-system rollout restart deployment bacalhau-controller-manager
kubectl -n bacalhau-system get pods
```

## Usage

Create a Job. Some samples can be found at `config/samples/pass-through-spec`. 
This command below will create a Bacalhau Job, utilizing the Operator.
```shell
kubectl create -f config/samples/pass-through-spec/job_simple_hello_world.yaml
````

Check status of the job; it should resolve to be completed.
```shell
kubectl -n bacalhau-system get BacalhauJob simple-hello-world-1
```

Describe the job to see the actual output:
```shell
kubectl -n bacalhau-system describe BacalhauJob simple-hello-world-1
```

* Grab the job ID from the status and check the status of the job in Bacalhau if you want to.
```bash
bacalhau describe <job ID> | less
```

There is currently a limitation with the Job updates, which is being worked on (a new feature to be added to bacalhau itself.)

## Prerequisites for development
* Kubernetes cluster- although any Kubernetes cluster(with recent version) would work, the light weight option would be to use [KCP](https://github.com/kcp-dev/kcp) as KCP doesn't have any orchestration components.
* Go 1.20+ installed 
* Bacalhau CLI installed

### Setup
* Clone the repo
* Run `kubectl create -f config/crd/bases/` to create the CRD
* Run `make run` to run the operator

### TODO
* Add support for WASM
* Accept input locations

## Publishing New Operator Docker Image

1. Make sure you have access to Github Image Registry. 
2. Bump the version of the image in the Makefile
3. Make sure you have built the CRD using the above command.
4. Run `make docker-build-multiarch` to build and publish the image.

### Contributing
Please feel free to open issues for any bugs or feature requests. Pull requests are welcome too.

## Note:
Project is based on Harsh Thakur's operator https://github.com/RealHarshThakur/bacalhau-operator.