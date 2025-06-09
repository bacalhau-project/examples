# Bacalhau Operator

This project aims to use Kubernetes as control plane with [Bacalhau](https://docs.bacalhau.org/) as the orchestrator.

> [!WARNING]
> This is a basic operator not meant for production use, yet.

## Prerequisites

To deploy this operator, you need to have access to a Kubernetes cluster. If you do not have access to one, an easy solution is to install [Minikube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fmacos%2Farm64%2Fstable%2Fhomebrew) with the [docker driver](https://minikube.sigs.k8s.io/docs/drivers/docker/).

Additionally, you need access to a Bacalhau Network. If you do not already have one, you can create a new network using the [Expanso Cloud](https://cloud.expanso.io/) free tier. If you are using Expanso Cloud, [see the section below](#installation-of-the-operator) about how to connect this K8s operator to it.

If you are using a locally deployed Bacalhau orchestrator, you need to make sure the K8S operator pods have network access to the Orchestrator API endpoint.

## Deciding on the Bacalhau Network

### Expanso Cloud

If you are using Expanso Cloud, note of the Endpoint provided to you when a network is provisioned as you need it to deploy the operator. For example, your Expanso Cloud Network endpoint might look like this: `https://g4hycm9u9ayp55.us1.cloud.expanso.io:1234`.

> [!NOTE]
> The port is mandatory.

Additionally, Expanso Cloud provides you with an API key. Take a note of it, as you also need it for the operator deployment.

### Self-hosted Bacalhau

If you are using a self-hosted Bacalhau cluster, then you need to make sure that the Operator Pods has network access to the Bacalhau Operator. This really depends on your setup.

For example, if you are using MiniKube, you can use `http://host.minikube.internal:1234` as the endpoint for the Orchestrator. This leverages the internal `host.minikube.internal` minikube DNS name that routes to your localhost.

Additionally, if you have deployed your Bacalhau cluster with Authentication enabled, you need to make note of the API Key, or Username/Password used.

### Default API Endpoint

> [!NOTE]
> The operator defaults the Bacalhau Endpoint to `http://bootstrap.production.bacalhau.org:1234/` which is a public testing network. We recommend using Expanso Cloud instead for easier experimentation.

## Installation of the Operator

In `bacalhau-operator.yaml`, change `API_Endpoint` to the Bacalhau Orchestrator Endpoint that you chose above. For example, if you chose Expanso Cloud, your endpoint looks like `https://g4hycm9u9ayp55.us1.cloud.expanso.io:1234`.

After updating the endpoint, run:

```bash
kubectl apply -f bacalhau-operator.yaml
```

This creates a `bacalhau` namespace, deploys the job controller, and the needed CustomResourceDefinitions (CRDs).

If your Bacalhau cluster has authentication enabled, you need to update the `API_Key` secret, and restart the Operator deployment.

For example, if the `API_KEY` is `abc123abc123abc123`, run the command below to update the key (make sure to replace the value of the API_KEY with your own key):

```shell
kubectl create secret generic bacalhau-api-credentials \
  --namespace bacalhau-system \
  --from-literal=API_KEY=abc123abc123abc123 \
  --dry-run=client -o yaml | kubectl apply -f -
```

Then, redeploy the Operator (make sure the Pods are running after the restart):

```shell
kubectl -n bacalhau-system rollout restart deployment bacalhau-controller-manager
kubectl -n bacalhau-system get pods
```

## Usage

Create a Job. You can find some examples in the `config/samples/pass-through-spec` folder.
This command below creates a Bacalhau Job with the Operator.

```shell
kubectl create -f config/samples/pass-through-spec/job_simple_hello_world.yaml
```

Check status of the job. It should resolve to completed.

```shell
kubectl -n bacalhau-system get BacalhauJob simple-hello-world-1
```

Describe the job to see the actual output:

```shell
kubectl -n bacalhau-system describe BacalhauJob simple-hello-world-1
```

Grab the job ID from the status and check the status of the job in Bacalhau:

```bash
bacalhau describe <job ID> | less
```

> [!NOTE]
> There is currently a limitation with Job updates, which is being worked on (a new feature to be added to Bacalhau itself.)

## Prerequisites for development

- Kubernetes cluster. Although any Kubernetes cluster (with recent version) would work, a light weight option is to use [KCP](https://github.com/kcp-dev/kcp) as KCP doesn't have any orchestration components.
- Go 1.20+ installed
- Bacalhau CLI installed

### Setup

- Clone the repo
- Run `kubectl create -f config/crd/bases/` to create the CRD
- Run `make run` to run the operator

### TODO

- Add support for WASM
- Accept input locations

## Publishing New Operator Docker Image

1. Make sure you have access to Github Image Registry.
2. Bump the version of the image in the Makefile
3. Make sure you have built the CRD using the above command.
4. Run `make docker-build-multiarch` to build and publish the image.

### Contributing

Please feel free to open issues for any bugs or feature requests. Pull requests are welcome too.

## Note:

Project is based on Harsh Thakur's operator https://github.com/RealHarshThakur/bacalhau-operator.
