---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: 0.13
    jupytext_version: 1.11.5
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# VELOX

Video airbornE Longwave Observations within siX channels

```{code-cell} ipython3
import eurec4a
from IPython.display import Markdown

meta = eurec4a.get_meta()
Markdown(meta["VELOX"]["description"])
```

The PI during EUREC4A was Michael Schäfer (University Leipzig). 

If you have questions or if you would like to use the data for a publication, please don't hesitate to get in contact with the dataset authors as stated in the dataset attributes `contact` or `author`.

```{note}
No data available for the transfer flights (first and last) and the first local research flight.
```

## Get data
To load the data we first load the [EUREC4A intake catalog](https://github.com/eurec4a/eurec4a-intake#eurec4a-intake-catalogue) and list the available datasets from VELOX.  
Currently, there is a cloud mask product available.

```{code-cell} ipython3
cat = eurec4a.get_intake_catalog(use_ipfs="QmahMN2wgPauHYkkiTGoG2TpPBmj3p5FoYJAq9uE9iXT9N")
list(cat.HALO.VELOX)
```

```{code-cell} ipython3
ds = cat.HALO.VELOX.cloudmask["HALO-0205"].to_dask()
ds
```

## What does the VELOX image look like at a specific dropsonde launch?  
We can use the [flight segmentation](https://github.com/eurec4a/flight-phase-separation#segmentation-of-flights-during-eurec4a) information to select a dropsonde and further extract the corresponding VELOX image taken at the time of the dropsonde launch.  
In particular, we select the first dropsonde with the quality flag `GOOD` from the second `circle` on February 5.  

### Get dropsonde ID
(0) we read the meta data and extract the segment IDs

```{code-cell} ipython3
meta = eurec4a.get_flight_segments()
```

```{code-cell} ipython3
segments = [{**s,
             "platform_id": platform_id,
             "flight_id": flight_id
            }
            for platform_id, flights in meta.items()
            for flight_id, flight in flights.items()
            for s in flight["segments"]
           ]
```

(1) we extract the segment ID of the second `circle`

```{code-cell} ipython3
import datetime

segments_ordered_by_start_time = list(sorted(segments, key=lambda s: s["start"]))
circles_Feb05 = [s["segment_id"]
                 for s in segments_ordered_by_start_time
                 if "circle" in s["kinds"]
                 and s["start"].date() == datetime.date(2020,2,5)
                 and s["platform_id"] == "HALO"
                ]
second_circle_Feb05 = circles_Feb05[1]
second_circle_Feb05
```

(2) we extract the ID of the first dropsonde with flag `GOOD` in this circle

```{code-cell} ipython3
segments_by_segment_id = {s["segment_id"]: s for s in segments}
first_dropsonde = segments_by_segment_id[second_circle_Feb05]["dropsondes"]["GOOD"][0]
first_dropsonde
```

### What is the corresponding launch time of the selected sonde?
So far, we only made use of the flight segmentation meta data. The launch time to a given sonde is stated in the [JOANNE](https://github.com/Geet-George/JOANNE/tree/master/joanne/Level_3#level%E2%80%943) dataset (see also book chapter {doc}`dropsondes`). 
We use again the intake catalog to load the JOANNE dataset and extract the launch time to the selected dropsonde by it's sonde ID.

```{code-cell} ipython3
dropsondes = cat.dropsondes.JOANNE.level3.to_dask()
```

```{code-cell} ipython3
sonde_dt = dropsondes.sel(sonde_id=first_dropsonde).launch_time.values
sonde_dt
```

### Cloud mask plot
Finally, we plot the VELOX image closest in time to the dropsonde launch.  
The y-axis is in flight direction and the image consists of 640 pixel by 512 pixels. The corresponding pixel viewing sensor zenith and azimuth angles are given by the dataset variables `vza` and `vaa`.

```{code-cell} ipython3
ds_sel = ds.cloud_mask.sel(time=sonde_dt, method="nearest")
```

```{code-cell} ipython3
%matplotlib inline
import matplotlib.pyplot as plt
plt.style.use("./mplstyle/book")

fig, ax = plt.subplots()

cax = ds_sel.plot(ax=ax,
                  cmap=plt.get_cmap('Greys', lut=4),
                  vmin=-1.5, vmax=2.5,
                  add_colorbar=False
                  )
cbar = fig.colorbar(cax, ticks=ds.cloud_mask.flag_values)
cbar.ax.set_yticklabels(ds.cloud_mask.flag_meanings.split(" "));

ax.set_title(f"VELOX cloud mask at {sonde_dt}");
```

What are the image cloud fraction lower and upper bounds?

```{code-cell} ipython3
cfmin = ds.CF_min.sel(time=sonde_dt, method="nearest").values
cfmax = ds.CF_max.sel(time=sonde_dt, method="nearest").values
print(f"Image minimum cloud fraction (most likely cloudy): {cfmin:.2f}")
print(f"Image maximum cloud fraction (most likely and probably cloudy) :{cfmax:.2f}")
```

## Cloud fraction time series from the second circle on February 5

We also want to show a time series of cloud fraction and use the segment ID from the second circle to extract and save the segment information to the variable `seg`. We can later use the segments start and end times to select the data in time.

```{code-cell} ipython3
seg = segments_by_segment_id[second_circle_Feb05]
```

The dataset variable `CF_min` provides a lower bound to cloud fraction estimates based on the cloud mask flag `most_likely_cloudy`, while `CF_max` provides an upper bound by including the uncertain pixels labeled `probably cloudy`.

```{code-cell} ipython3
selection = ds.sel(time=slice(seg["start"], seg["end"]))

with plt.style.context("mplstyle/wide"):
    fig, ax = plt.subplots()
    selection.CF_min.plot(color="k", label="most_likely_cloudy")
    selection.CF_max.plot(color="grey", label="most_likely_cloudy\nand probably_cloudy")
    ax.axvline(sonde_dt, color="C3", label="sonde launch time")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Cloud fraction")
    ax.set_title("Second circle on February 5")
    ax.legend(title="Cloud mask flags", bbox_to_anchor=(1,1), loc="upper left");
```
