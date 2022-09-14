---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.12
    jupytext_version: 1.8.1
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# SMART dataset

The following script exemplifies the access and usage of SMART data measured during EUREC4A. The Spectral Modular Airborne Radiation measurement sysTem (SMART) measures downward irradiances in the solar spectral range between 300 nm and 2200 nm.

More information on the dataset can be found in {cite:t}`Stevens:2019` and {cite:t}`Wendisch:2001`. If you have questions or if you would like to use the data for a publication, please don't hesitate to get in contact with the dataset authors as stated in the dataset attributes `contact` or `author`.

## Get data
* To load the data we first load the EUREC4A meta data catalogue. More information on the catalog can be found [here](https://github.com/eurec4a/eurec4a-intake#eurec4a-intake-catalogue).

```{code-cell} ipython3
import eurec4a
```

```{code-cell} ipython3
cat = eurec4a.get_intake_catalog(use_ipfs="QmahMN2wgPauHYkkiTGoG2TpPBmj3p5FoYJAq9uE9iXT9N")
list(cat.HALO.SMART)
```

* We can further specify a product and a flight and obtain the dataset using `to_dask`.

```{note}
Have a look at the attributes of the xarray dataset `ds_smart` for all relevant information on the dataset, such as author, contact, or citation infromation.
```

```{code-cell} ipython3
ds_smart = cat.HALO.SMART.spectral_irradiances['HALO-0205'].to_dask()
ds_smart
```

The available dataset includes irradiances for six selected wavelengths (422nm, 532nm, 648nm, 858nm, 1238nm, 1638nm). The full dataset is available on demand. Contact the dataset authors as stated in the dataset attributes `contact`.

First Quickplot of whole flight (one wavelength)

```{code-cell} ipython3
%matplotlib inline
import matplotlib.pyplot as plt
plt.style.use("./mplstyle/book")

ds_smart.F_down_solar_wl_422.plot();
```

## Load HALO flight phase information
All HALO flights were split up into flight phases or segments to allow for a precise selection in time and space of a circle or calibration pattern. For more information have a look at the respective [github repository](https://github.com/eurec4a/halo-flight-phase-separation).

```{code-cell} ipython3
meta = eurec4a.get_flight_segments()
```

We select the flight phase we are interested in, e.g. the second circle on February 5 by it’s segment_id.

```{code-cell} ipython3
segments = {s["segment_id"]: {**s, "flight_id": flight["flight_id"]}
             for platform in meta.values()
             for flight in platform.values()
             for s in flight["segments"]
            }
seg = segments["HALO-0205_c2"]
```

We transfer the information from our flight segment selection to our radar and radiometer data in the xarray dataset.

```{code-cell} ipython3
ds_smart_selection = ds_smart.sel(time=slice(seg["start"], seg["end"]))
```

## Plots

+++

We plot the spectral irradiances from different wavelengths measured with SMART during the selected flight segment.

```{code-cell} ipython3
fig, ax = plt.subplots()
wl_list=[422,532,648,858,1238,1638]
for i in wl_list:
    ds_smart_selection[f'F_down_solar_wl_{i}'].plot(label =f'{i} nm')
ax.legend()
ax.set_ylabel('Spectral downward irradiance / Wm$^{-2}$nm$^{-1}$')
None
```
