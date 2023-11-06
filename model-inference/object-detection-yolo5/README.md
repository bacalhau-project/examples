# ML Inference with Bacalhau and YOLO

In this tutorial, we'll guide you through the steps to set up and run machine learning inference using Bacalhau and YOLO. The process is broken down into these key areas:

1. **Hardware Provisioning**: Setting up a Requester node and one or more Compute nodes.
2. **Bacalhau Installation**: Installing Bacalhau and its dependencies on each node.
3. **Data Preparation**: Preparing the dataset for inference.
4. **Bacalhau Configuration**: Configuring each node for inference using the container found in thie project.
5. **Performing Inference**: Executing a YOLO-based inference job on the dataset.
6. **Result Analysis**: Reviewing the inference results.

## Hardware Provisioning

- **Requester Node**
  
    Let's set up a Requester node first. You'll need to refer to the IP address of this node as `$REQUESTER_NODE_HOST` in later steps.
    
    Recommended Requirements:
    - Number of Instances: 1
    - Disk: 25-100GB
  - CPU: 4-8vCPU
    - Memory: 8-16GB
    
  
- **Compute Node(s)**
  
    These nodes will perform the actual computation. Their IP addresses should be referred to as `$COMPUTE_NODE_HOST`.
    
    Recommended Requirements:
    
    - Number of Instances: 1-N
    - Disk: 32-500GB
    - CPU: 1-32vCPU
    - Memory: 8-64GB
    - GPU/TPU: 1 (Optional for better performance of ML Inference)

> Note: For GPU-equipped nodes, follow the configuration steps in [this guide](https://docs.bacalhau.org/running-node/gpu).

Install Docker on each compute node, ensuring that the Docker daemon is accessible to the Bacalhau-running user. For Docker installation instructions, refer to [this guide](https://docs.bacalhau.org/running-node/quick-start#install-docker).

## Data Preparation

Gather the video files designated for inference. Distribute them among your compute nodes, ensuring at least one video file is in a directory named `$INFERENCE_VIDEOS` (e.g., `/video_dir`). This directory will be made accessible to Bacalhau during configuration. For sample videos, access the `videos` directory of this project or download samples from [here](https://orange-elderly-carp-967.mypinata.cloud/ipfs/QmSw1vJGmYZu2KeNr9nrEFCWARFq6EJHbscXFHNuEhDf4i/).

## Bacalhau Installation

Follow these steps on each node:

1. Access each node (via SSH, PuTTY, etc.).
2. Issue the installation command:
   ```bash
   $ curl -sL https://get.bacalhau.org/install.sh | bash

## Configure & Run Bacalhau

### On the Requester Node

Log in to `$REQUESTER_NODE_HOST` and start the Bacalhau Requester service:

```bash
$ env BACALHAU_ENVIRONMENT=local bacalhau serve --node-type=requester
```

### On Compute Node(s)

Log in to each `$COMPUTE_NODE_HOST` and start the Bacalhau Compute service:

```bash
$ env BACALHAU_ENVIRONMENT=local bacalhau serve --node-type=compute --allow-listed-local-paths=$INFERENCE_VIDEOS --peer=/ip4/$REQUESTER_NODE_HOST/tcp/1235
```

Optionally, pull the YOLO container image used for inference on each compute node:

```bash
$ docker pull docker.io/bacalhauproject/yolov5-7.0:v1.1
```

### Verify Configuration

Back on the `$REQUESTER_NODE_HOST`, validate your setup:

```bash
$ bacalhau node list
```

The output should display a `Requester` node and one or more `Compute` nodes.
## Execute ML Inference

From `$REQUESTER_NODE_HOST`, initiate an inference job:

```bash
$ bacalhau docker run --target=all --input file://$INFERENCE_VIDEOS:/videos docker.io/bacalhauproject/yolov5-7.0:v1.1
```

> Note: Replace `$INFERENCE_VIDEOS` with the actual directory path.

The Job ID, displayed in the output, is unique; refer to it as `$JOB_ID`.

### Customizing INference Settings:

As indicated by the Dockerfile in the project the default values will be passed to YOLO when conducting inference:

1. `--classes: "1 2 3 4 5 6 7 9 10 11 12"`
   1. For a list of class definitions see this [link](https://github.com/ultralytics/yolov5/blob/34cf749958d2dd3ed1205f6bb07e0f20f6e2372d/data/coco.yaml).
2. `--conf-thres:0.7`
3. `--weights=/model/yolov5s.pt`

You can substitute these values with your own by passing environment variables to the `bacalhau docker run` command, for example:

1. To use a different set of classes:
   ```bash
   $ bacalhau docker run --target=all --input=file://$INFERENCE_VIDEOS:/videos \
   --env=CLASSES="0" \
   docker.io/bacalhauproject/yolov5-7.0:v1.1
   ```

2. To use a different confidence threshold:

   ```bash
   $ bacalhau docker run --target=all --input=file://$INFERENCE_VIDEOS:/videos \
   --env=CONF_THRES=".95" \
   docker.io/bacalhauproject/yolov5-7.0:v1.1
   ```

3. To use different weights:

   ```bash
   $ bacalhau docker run --target=all --input=file://$INFERENCE_VIDEOS:/videos \
   --input=https://github.com/ultralytics/yolov5/releases/download/v6.2/yolov5x.pt:/model \
   --env=WEIGHTS_PATH=/model/yolov5x.pt \
   docker.io/bacalhauproject/yolov5-7.0:v1.1
   ```

4. To use multiple environment variables together:
   ```bash
   $ bacalhau docker run --target=all --input=file://$INFERENCE_VIDEOS:/videos \
   --input=https://github.com/ultralytics/yolov5/releases/download/v6.2/yolov5x.pt:/model \
   --env=WEIGHTS_PATH=/model/yolov5x.pt \
   --env=CONF_THRES=".95" \
   --env=CLASSES="0" \
   docker.io/bacalhauproject/yolov5-7.0:v1.1
   ```

## Analyzing Results

You can follow the logs produced by your inference job by issuing the following command:
```bash
$ bacalhau logs -f $JOB_ID
```

You can inspect the state of the job by issuing the following command:
```bash
$ bacalhau describe $JOB_ID
```

Once your job is complete, you can download the results by issuing the following command:
```bash
$ bacalhau get --raw $JOB_ID
```

With this tutorial, you should have a clear path to executing and managing your YOLO-based inference tasks with Bacalhau.