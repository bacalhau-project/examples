# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.13.8
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Cloud masks
#
# Different instruments, by virtue of their differing measurement principle and footprint, see clouds in different ways. To provide an overview of the cloud fields sampled by HALO during EUREC4A, a cloud mask is created for each cloud sensitive instrument.  
# In the following, we compare the different cloud mask products for a case study on 5 February and further provide a statistical overview for the full campaign period.
#
# More information on the dataset can be found in Konow et al. (in preparation). If you have questions or if you would like to use the data for a publication, please don't hesitate to get in contact with the dataset authors as stated in the dataset attributes `contact` or `author`.

# %%
import eurec4a
import numpy as np
import xarray as xr
import matplotlib as mpl

from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib.colors import LogNorm

# %% [markdown]
# We generally don't support ignoring warnings, however, we do so in this notebook to suppress warnings originating from zero division. Unfortunately, we coudn't find another way to handle the warnings. If you have an idea, please make a pull request and change it :)

# %%
import warnings
warnings.filterwarnings("ignore")


# %% [markdown]
# ## Cloud cover functions
# We define some utility functions to extract (circle) cloud cover estimates from different datasets assuming that the datasets follow a certain flag meaning convention.  
#
# In particular, we define a **minimum cloud cover** based on the cloud mask flag `most_likely_cloudy` and a **maximum cloud cover** combining the flags `most_likely_cloudy` and `probably_cloudy`. The cloud mask datasets slightly vary in their flag definition for cloud free conditions and their handling of unvalid measurements which is taken care of by the following functions.

# %%
def _isvalid(da):
    meanings = dict(zip(da.flag_meanings.split(" "), da.flag_values))
    return ~(np.isnan(da) | ("unknown" in meanings and da==meanings["unknown"]))

def _cloudy_max(da):
    meanings = dict(zip(da.flag_meanings.split(" "), da.flag_values))
    return (da==meanings["most_likely_cloudy"]) | (da==meanings["probably_cloudy"])

def _cloudy_min(da):
    meanings = dict(zip(da.flag_meanings.split(" "), da.flag_values))
    return da==meanings["most_likely_cloudy"]

def cfmin(ds):
    sumdims = [d for d in ds.cloud_mask.dims if d != "time"]
    return (_cloudy_min(ds.cloud_mask).sum(dim=sumdims)
            / _isvalid(ds.cloud_mask).sum(dim=sumdims))

def cfmax(ds):
    sumdims = [d for d in ds.cloud_mask.dims if d != "time"]
    return (_cloudy_max(ds.cloud_mask).sum(dim=sumdims)
            / _isvalid(ds.cloud_mask).sum(dim=sumdims))

def correct_VELOX(ds):
    return ds.assign(CF_min=ds.CF_min.where((ds.CF_min >=0 ) & (ds.CF_min <= 1)),
                     CF_max=ds.CF_max.where((ds.CF_max >=0 ) & (ds.CF_max <= 1)))

def ensure_cfminmax(ds):
    if "CF_min" not in ds:
        ds = ds.assign(CF_min=cfmin)
    if "CF_max" not in ds:
        ds = ds.assign(CF_max=cfmax)
    ds.CF_min.load()
    ds.CF_max.load()
    return correct_VELOX(ds)

from multiprocessing.pool import ThreadPool

def load_cloudmask_dataset(cat_item):
    # load in parallel as this function is mainly limited by the network roundtrip time
    p = ThreadPool(20)
    return ensure_cfminmax(xr.concat(list(p.map(lambda v: v.get().to_dask().chunk(),
                                                cat_item.values())),
                                     dim="time",
                                     data_vars="minimal"))


# %% [markdown]
# ## Get data
# We use the [eurec4a intake catalog](https://github.com/eurec4a/eurec4a-intake) to access the data files.

# %%
cat = eurec4a.get_intake_catalog(use_ipfs="QmahMN2wgPauHYkkiTGoG2TpPBmj3p5FoYJAq9uE9iXT9N")
list(cat.HALO)

# %% [markdown]
# For each instrument, we extract the data from individual flights and concatenate them to campaign-spanning datasets for the cloud mask files.

# %%
cat_cloudmask = {
    "WALES": cat.HALO.WALES.cloudparameter,
    "HAMP Radar": cat.HALO.UNIFIED.HAMPradar_cloudmask,
    "specMACS": cat.HALO.specMACS.cloudmaskSWIR,
    "HAMP Radiometer": cat.HALO.UNIFIED.HAMPradiometer_cloudmask,
    "KT19": cat.HALO.KT19.cloudmask,
    "VELOX": cat.HALO.VELOX.cloudmask,
}

# %%
data = {k: load_cloudmask_dataset(v) for k, v in cat_cloudmask.items()}

# %% [markdown]
# We have a look at the time periods spanned by the individual datasets: The datasets `HAMP Radar`, `HAMP Radiometer`, and `specMACS` include measurements from the transfer flights on 19 January to Barbados and on 18 February back over the Atlantic to Europe. The datasets `WALES`, `KT19`, and `VELOX` are limited to the 13 local research flights between 22 January and 15 February.

# %%
for k, v in data.items():
    print(f"{k}: {v.isel(time=0).time.values} -  {v.isel(time=-1).time.values}")
