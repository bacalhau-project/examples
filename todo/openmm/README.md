# Openmm


## Build and test the docker image locally

```bash
docker build -t winderresearch/bacalwow-openmm .

mkdir -p output

docker run \
    -v output:/project/output \
    winderresearch/bacalwow-openmm
```































