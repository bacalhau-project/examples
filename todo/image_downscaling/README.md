# Example custom packages

> ⚠️ This example may be outdated and soon will be reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.

## Background

The intent of this example is to show how to install custom packages during install.

## Setup

**MAKE SURE YOU ARE RUNNING ON ipfs v0.11!!!!!!!!!!!!!**

```bash
export file_path=./high_quality_picture.jpg
cid=$(IPFS_PATH=/tmp/bacalhau-ipfs3163549147 ipfs add -q $file_path)
sudo apt-get -y update && sudo apt-get install -y graphicsmagick && \
    gm convert high_quality_picture.jpg -quality 20% -colorspace Gray gray_scale.jpg && IPFS_PATH= ipfs add 
```

**BUG - If you're not outputting to stdout, how do you record?**
