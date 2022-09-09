
# Background

> ⚠️ This example may be outdated and soon will up reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.


Scientific Purpose of the workload:

The Surface Ocean CO₂ Atlas (SOCAT) contains measurements of the [fugacity](https://en.wikipedia.org/wiki/Fugacity) of CO2 in seawater around the globe. But in order to calculate how much carbon the ocean is taking up from the atmosphere, these measurements need to be converted to partial pressure of CO2. We will convert the units by  combining measurements of the surface temperature and fugacity.  Python libraries (xarray, pandas, numpy) and the pyseaflux package facilitate this process.

References:
- https://www.socat.info/
- https://seaflux.readthedocs.io/en/latest/api.html?highlight=fCO2_to_pCO2#pyseaflux.fco2_pco2_conversion.fCO2_to_pCO2
- https://github.com/lgloege/bacalhau_socat_test/blob/main/main.py
- https://github.com/wesfloyd/bacalhau_socat_test


# Running the demo

To test locally:
1) Clone the repository
2) Invoke the docker container:
```
docker run -v $(pwd)/input:/project/input \
	-v output:/project/output \
	wesfloyd/bacalwow-socat-test
```


To run on [Bacalhau](https://github.com/filecoin-project/bacalhau):
1) Upload the input directory to IPFS (via [Web3.storage folder upload script](https://web3.storage/docs/#create-the-upload-script))
    cd web3storage
    npm install
    node put-files.js --token=[TOKEN] ../input

2) Use the CID of the input directory to run the job on Bacalhau

```
bacalhau docker run -v bafybeibwv2ccdr5u3esjaeu4fh5b2cbgbixolk33wg4pj6t4lqvrkf7qja:/project/input \
	-o output:/project/output \
	wesfloyd/bacalwow-socat-test

bacalhau list

bacalhau describe [JOB_ID]

bacalhau get [JOB_ID]
```
This job will require approx 100s to complete on a Bacalhau node.
