# Overview

This recipe contains information and scripts to produce performance results for the Llama 3.1 training workload. The scripts help perform environment setup, dataset setup, and launch benchmark jobs.
This variant of the workload is best-suited for GPU clusters with

* At least 64 GPUs with at least 80 GB memory each. Training of this 70-billion parameter variant of the workload will not fit on fewer GPUs with less memory.
* H100 GPUs. This workload runs with BF16 or FP8, which are both supported by H100 GPUs.

# Expected Performance

Performance for Llama 3.1 training is measured by seconds per iteration, or in other words seconds per training step. This metric is logged for every training step in a .out file which is generated inside of the `$STAGE_PATH/results/$GSW_VERSION/${DTYPE}/70b/$JOB_TOTAL_GPUS` folder. 

Since the performance fluctuates significantly at the beginning, we are using the last training step timing to obtain throughput value.

```shell
grep train_step_timing results/*.out
Epoch 0: : 100%|██████████| 100/100 [20:15<00:00, reduced_train_loss=6.370, global_step=99.00, consumed_samples=12800.0, train_step_timing in s=11.20]
```

To obtain throughput as a tokens per second measurement, follow this formula: 
```shell
(sequence length) * (global batch size) / (training_step_timing) = (throughput in tokens per second)
```

E.g. 8192 * 128 / 11.31 = 92712

To calculate time to train estimate:
```shell
(total tokens) / (throughput in tokens per second) / (number of seconds in a day) = (time to train in days) 
```
E.g. 1e12 / 92712 / 86400 = 124.84 days 


To calculate the model flops utilization (MFU):
```shell
MFU = (global batch size) * (model flops) / (training step time) / (number of GPUs) / (peak GPU FLOPS)
```

The peak theoretical throughput for H100 FP8 is 1979 TFLOPS and for H100 BF16 is 989 TFLOPS.

The model flops for Llama 3.1 70b for GBS=1 is 3.94E+15. Calculation shown [here](#notes).

E.g. Llama 3.1 70b FP8 on 64x H100 GPUs (GBS=128)
```shell
peak FLOPS for H100 = 1979 TFLOPS 
training step time = 11.31
model flops = 3.94E+15
MFU = 128 * 3.94E+15 / 11.31 / 64 / 1979E+12 = 35.21% 
```

| Llama 3.1 70b 24.09 BF16 (TP=4, PP=4, CP=2, VP=5, MBS=1, GA=64) | Throughput on 64x H100 GPUs (GBS=128) | Throughput on 128x H100 GPUs (GBS=256) | Throughput on 256x H100 GPUs (GBS=512) | Throughput on 512x H100 GPUs (GBS=1024) | Throughput on 1024x H100 GPUs (GBS=2048) | Throughput on 2048x H100 GPUs (GBS=4096)
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Training step time (seconds per step) | 14.72  | 14.73  | 14.8   | 14.89  | 14.92   | 14.98
| Throughput in tokens per second       | 71235  | 142373 | 283399 | 563372 | 1124478 | 2248957
| Model flops utilization               | 54.10% | 54.06% | 53.81% | 53.48% | 53.38%  | 53.38%
| Time to train 1T tokens in days       | 162.48 | 81.29  | 40.84  | 20.54  | 10.29   | 5.15

| Llama 3.1 70b 24.09 FP8 (TP=4, PP=4, CP=2, VP=5, MBS=1, GA=64) | Throughput on 64x H100 GPUs (GBS=128) | Throughput on 128x H100 GPUs (GBS=256) | Throughput on 256x H100 GPUs (GBS=512) | Throughput on 512x H100 GPUs (GBS=1024) | Throughput on 1024x H100 GPUs (GBS=2048) | Throughput on 2048x H100 GPUs (GBS=4096)
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Training step time (seconds per step)   | 11.01  | 10.93  | 11.16  | 11.18  | 11.28   | 11.39
| Throughput in tokens per second         | 95239  | 191871 | 375834 | 750323 | 1487342 | 2945955
| Model flops utilization                 | 36.17% | 36.43% | 35.68% | 35.62% | 35.30%  | 34.96%
| Time to train 1T tokens in days         | 121.53 | 60.32  | 30.80  | 15.43  | 7.78    | 3.93

# Prerequisites

This recipe requires access to Llama 3.1. Instructions are below if needed.

# Request Access
A HuggingFace account is required and you will need to [create a HuggingFace access token](https://huggingface.co/settings/tokens) in order to run the training script. Add the generated token to your environment via ```export HF_TOKEN=<your token>```.

Access to Llama 3.1 must be requested through [Meta's website](https://llama.meta.com/llama-downloads/) then requested on the [HuggingFace Llama](https://huggingface.co/meta-llama/Meta-Llama-3.1-70B) page. The approval process is not automatic and could take a day or more.

# Prepare Environment

Create a staging area by running the attached setup.sh. The script converts the docker image from `nvcr.io/nvidia/nemo:24.09` to the `nvidia+nemo+24.09.sqsh` file under the $STAGE_PATH folder and copies NeMo Launcher code from the container. The setup script also downloads Llama3 tokenizer related files from HuggingFace [meta-llama/Meta-Llama-3-8B](https://huggingface.co/meta-llama/Meta-Llama-3-8B) repo using `HF_TOKEN` obtained in the previous step. **Note:** Llama3.1 8B and 70B use the same tokenizer and for this recipe we use the Llama 3 tokenizer.

```shell
# Set the path where all artifacts will be downloaded
export STAGE_PATH=<path to your shared file system folder> (e.g. /lustre/myproject/nemo)
# Set the Slurm partition to launch against
export SLURM_PARTITION="batch"
# Set the Slurm account to launch against
export SLURM_ACCOUNT="account_name"
# Set the number of GPUs per node according to Slurm's gres, this is usually 8 or null - https://slurm.schedmd.com/gres.html
export SLURM_GPUS_PER_NODE=null
# Set HuggingFace token
export HF_TOKEN=<your token>

# Run the setup
bash ./setup.sh
```

# Prepare Dataset
Pre-training a GPT-3 model requires a text-based dataset to be downloaded and pre-processed for the NeMo Framework to ingest the data optimally. [The Pile](https://huggingface.co/datasets/monology/pile-uncopyrighted) is often used as the dataset for pre-training models. The NeMo Framework contains helper scripts to download and pre-process the dataset. The following steps outline how to download and pre-process the dataset on DGX Cloud with an explanation of key points after.

Make sure `$STAGE_PATH/llama3.1-dataset/llama` contains tokenizer files downloaded from previous step.

Run the `generate_dataset.sh` script. The script launches several Slurm jobs that will download the dataset from The Pile, pre-process it and save it in a form suitable for subsequent training. The resulting dataset files will be saved under the `$STAGE_PATH/llama3.1-dataset` folder. The dataset creation may use up to 100GB. Make sure you have sufficient disk space available.


```shell
bash ./generate_dataset.sh
```

If the dataset generation step was successful there should be 2 idx and 2 bin files in the $STAGE_PATH/llama3.1-dataset folder.

```shell
my-llama_00_text_document.bin
my-llama_00_text_document.idx
my-llama_01_text_document.bin
my-llama_01_text_document.idx
```

If that is not the case, check the log files in: $STAGE_PATH/results.data_preparation


# Run Training

NeMo Launcher is using the Hydra framework to process command line arguments and pass them down as hyperparameters to a multi-node job performing the training.

The training will run for the first 50 steps and will stop afterwards. Log files and results will be located under the `$STAGE_PATH/results/$GSW_VERSION/${DTYPE}/70b/$JOB_TOTAL_GPUS` folder.

Below is a command template for launching Llama 3.1 70b model training.
```shell
DTYPE=<fp8/bf16> MODEL_SIZE=70b sbatch -A ${SLURM_ACCOUNT} -p ${SLURM_PARTITION} -N ${NUM_NODES} ./launch.sh
```

Where:
- `DTYPE` and `MODEL_SIZE` are **required** environment variables.
	- `DTYPE` can be either `fp8` or `bf16`.
	- `MODEL_SIZE` should be `70b` in this case.
- `NUM_NODES` can be calculate by `N_GPUS / N_GPUS_PER_NODE`, `N_GPUS_PER_NODE` is 8 for DGX H100, therefore for 128 GPUs scale, `NUM_NODES` should be `128 / 8 = 16`.

**Note:** it might be necessary to pass `--gres=gpu:8` to sbatch for certain clusters on encountering errors like GPU not found. See https://slurm.schedmd.com/gres.html

It is important to maintain these values for model parallelism settings in order to accurately assess performance results for completed jobs against expected baseline:
* `training.model.tensor_model_parallel_size=4`
* `training.model.pipeline_model_parallel_size=4`
* `training.model.virtual_pipeline_model_parallel_size=5`
* `training.model.context_parallel_size=2`

Global batch size ( training.model.global_batch_size) value should be set to ```<number of nodes> * 16. E.g., 16 * 16 = 256 (in the example above)```.

# Notes

```shell
model flops = (sequence length) * ((attention flops) + (mlp flops) + (embedding flops))

model flops breakdown:
    attention flops = 12 * (number of layers) * (hidden size)^2 * (1 + (number of query groups)/(number of attention heads) + (sequence length)/(hidden size))
    mlp flops = 18 * (number of layers) * (FFN size) * (hidden size)
    embedding flops = 6 * (vocab size) * (hidden size)

Llama 3.1 70b calculation: 
    sequence length = 8192
    attention flops = 12 * 80 * 8192^2 * (1 + 8/64 + 8192/8192) = 136,902,082,560
    mlp flops = 18 * 80 * 28672 * 8192 = 338,228,674,560
    embedding flops = 6 * 128256 * 8192 = 6,304,038,912

    model flops = 8129 * (136,902,082,560 + 338,228,674,560 + 6,304,038,912) = 3.94E+15
```

