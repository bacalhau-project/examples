import eurec4a
import numpy as np
import xarray as xr

CFMIN_ATTRS = {
    "description": "Minimal possible cloud fraction",
    "long_name": "Minimal cloud fraction",
}
CFMAX_ATTRS = {
    "description": "Maximal possible cloud fraction",
    "long_name": "Maximal cloud fraction",
}

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
            / _isvalid(ds.cloud_mask).sum(dim=sumdims)).assign_attrs(CFMIN_ATTRS)

def cfmax(ds):
    sumdims = [d for d in ds.cloud_mask.dims if d != "time"]
    return (_cloudy_max(ds.cloud_mask).sum(dim=sumdims)
            / _isvalid(ds.cloud_mask).sum(dim=sumdims)).assign_attrs(CFMAX_ATTRS)

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

def load_cloudmask_dataset(cat_item):
    return ensure_cfminmax(xr.concat([v.get().to_dask().chunk() for v in cat_item.values()],
                                     dim="time",
                                     data_vars="minimal"))

def get_dataset(sensor):
    cat = eurec4a.get_intake_catalog(use_ipfs="QmahMN2wgPauHYkkiTGoG2TpPBmj3p5FoYJAq9uE9iXT9N")
    cat_cloudmask = {
        "WALES": cat.HALO.WALES.cloudparameter,
        "HAMP Radar": cat.HALO.UNIFIED.HAMPradar_cloudmask,
        "specMACS": cat.HALO.specMACS.cloudmaskSWIR,
        "HAMP Radiometer": cat.HALO.UNIFIED.HAMPradiometer_cloudmask,
        "KT19": cat.HALO.KT19.cloudmask,
        "VELOX": cat.HALO.VELOX.cloudmask,
    }
    return load_cloudmask_dataset(cat_cloudmask[sensor])


TARGET_CHUNKS = [
    {"time": 2**18},
    {"time": 2**14, "angle": 2**4},
    {"time": 2**10, "x": 2**4, "y": 2**4},
    {"x": 2**10, "y": 2**10},
]

def rechunk_var(v):
    for tc in TARGET_CHUNKS:
        if set(v.dims) == set(tc):
            chunks = tc
            break
    else:
        raise ValueError(f"no predefined chunking for {set(v.dims)}")
    v = v.chunk(chunks)
    v.encoding = {}
    return v

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("sensor")
    args = parser.parse_args()
    
    ds = get_dataset(args.sensor)
    ds_out = ds.assign(**{name: rechunk_var(v) for name, v in ds.items()})
    print(ds_out)
    encoding = {
        "time": {
            "dtype": "f8",
            "units": "seconds since 2020-01-01",
        },
    }
    ds_out.to_zarr(f"{args.sensor}.zarr", encoding=encoding)
    return 0

if __name__ == "__main__":
    exit(main())
