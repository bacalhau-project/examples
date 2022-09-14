# How to EUREC4A

> ⚠️ This example may be outdated and soon will be reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.

[EUREC4A](https://eurec4a.eu/), the Field Study, is an international initiative in support of the World Climate Research Programme's Grand Science Challenge on Clouds, Circulation and Climate Sensitivity. EUREC4A will take place between 20 January and 20 February 2020 with operations based out of Barbados. 

EUREC4A aims at advancing understanding of the interplay between clouds, convection and circulation and their role in climate change: How resilient or sensitive is the shallow cumulus cloud amount to variations in the strength of convective mixing, surface turbulence and large-scale circulations?

Different instruments, by virtue of their differing measurement principle and footprint, see clouds in different ways. To provide an overview of the cloud fields sampled by HALO during EUREC4A, a cloud mask is created for each cloud sensitive instrument.

[Original EUREC4A workload in github](https://github.com/eurec4a/how_to_eurec4a/blob/master/how_to_eurec4a/cloudmasks.md)


# Running the demo


To run on [Bacalhau](https://github.com/filecoin-project/bacalhau):

```
bacalhau docker run \
  wesfloyd/bacalwow:eurec4a-analysis-v2 \
  -- /home/how_to_eurec4a/start-analysis
bacalhau list
bacalhau describe [JOB_ID]
bacalhau get [JOB_ID]
```
