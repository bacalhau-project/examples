#!/bin/bash

CWD=$(pwd)

ssh -i $CWD/BacalhauSpotInstancesKey.pub azureuser@$1

