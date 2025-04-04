# Bacalhau Operator

This project aims to use Kubernetes as controlplane with [Bacalhau](https://docs.bacalhau.org/) as the orchestrator. This is a very basic operator not meant for production use.

## Project is based on Harsh Thakur's operator https://github.com/RealHarshThakur/bacalhau-operator. 
## It was updated and expanded by Krzysztof Dreżewski

## Note: Minikube
Please note that the easiest setup to test this operator locally, is to install [Minikube](https://minikube.sigs.k8s.io/docs/start/?arch=%2Fmacos%2Farm64%2Fstable%2Fhomebrew) with the [docker driver](https://minikube.sigs.k8s.io/docs/drivers/docker/) . 
Please note that the `bacalhau-operator.yaml` defaults `APIHost` to `host.minikube.internal` where it expects the Orchestrator API server to be listening on the host. You can change the APIHost to any value that suites your setup.


## Installation of the operator
```bash
kubectl apply -f bacalhau-operator.yaml
```
This will create bacalhau namespace, deploy job controller and needed CRDs.

## Usage

* Create a Job CR, a samples can be found at config/samples
```bash
kubectl create -f config/samples/pass-through-spec/job_simple_hello_world.yaml
````

* Check status of the job
```bash
kubectl -n bacalhau get job simple-hello-world-1
```

* Grab the job ID from the status and check the status of the job in Bacalhau
```bash
bacalhau describe <job ID> | less
```

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


### Contributing
Please feel free to open issues for any bugs or feature requests. Pull requests are welcome too.
