# Example of sharding with video filters

> ⚠️ This example may be outdated and soon will be reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.

```bash
cid="Qmd9CBYpdgCLuCKRtKRRggu24H72ZUrGax5A9EYvrbC72j"
time bacalhau docker run \
  -v $cid:/inputs \
  --cpu 2 \
  --memory 1Gb \
  --wait \
  --wait-timeout-secs 10000 \
  binocarlos/video-resize-example \
  bash /entrypoint.sh /inputs /outputs
time bacalhau docker run \
  -v $cid:/inputs \
  --cpu 2 \
  --memory 1Gb \
  --wait \
  --wait-timeout-secs 10000 \
  --sharding-base-path "/inputs" \
  --sharding-glob-pattern "*.mp4" \
  --sharding-batch-size 1 \
  binocarlos/video-resize-example \
  bash /entrypoint.sh /inputs /outputs
```
