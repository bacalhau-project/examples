# Openmm Test

> ⚠️ This example may be outdated and soon will be reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.

## Background

[OpenMM](https://github.com/openmm/openmm) is a toolkit for molecular simulation. Physic based libraries like OpenMM are then useful for refining the structure and exploring functional interactions with other molecules. It provides a combination of extreme flexibility (through custom forces and integrators), openness, and high performance (especially on recent GPUs) that make it truly unique among simulation codes.

## Running the Demo
Example workload to validate [OpenMM](https://github.com/openmm/openmm) on [Bacalhau](bacalhau.org) via [workload onboarding](https://docs.bacalhau.org/getting-started/workload-onboarding)  


### To run on [Bacalhau](https://github.com/filecoin-project/bacalhau):
```bash
bacalhau docker run \
	-o output:/project/output \
	wesfloyd/bacalwow-openmm

bacalhau list

bacalhau describe [JOB_ID]

bacalhau get [JOB_ID]
```


### To Build and test the docker image locally
```bash

git clone https://github.com/wesfloyd/openmm-test.git

docker build -t wesfloyd/bacalwow-openmm .

mkdir output

docker run \
	-v output:/project/output \
	wesfloyd/bacalwow-openmm

docker push wesfloyd/bacalwow-openmm


```

### To create the Docker Image from scratch

```bash

docker run --name bacalwow-openmm -it conda/miniconda3

conda install -y -c conda-forge openmm
#python -m openmm.testInstallation


#this section will be omitted from Dockerfile
mkdir /project /project/output/ /project/input
cd /project
apt-get update && apt-get -y upgrade &&\
apt-get install -y wget sudo vim git
git clone https://github.com/wesfloyd/openmm-test.git
cp openmm-test/run_openmm_simulation.py  .
cp openmm-test/input/2dri-processed.pdb ./input
python run_openmm_simulation.py

#exit
#docker commit <CONTAINER_ID> wesfloyd/bacalwow-openmm
#docker push wesfloyd/bacalwow-openmm

```
































