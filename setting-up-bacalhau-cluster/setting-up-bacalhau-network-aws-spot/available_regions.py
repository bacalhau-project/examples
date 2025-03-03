# AWS regions with spot instances suitable for Docker and containers
# This file is auto-generated by get_available_regions.py

AVAILABLE_REGIONS = [
    "af-south-1",
    "ap-east-1",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-south-1",
    "ap-south-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-southeast-3",
    "ap-southeast-4",
    "ap-southeast-5",
    "ca-central-1",
    "ca-west-1",
    "eu-central-1",
    "eu-central-2",
    "eu-north-1",
    "eu-south-1",
    "eu-south-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "me-central-1",
    "me-south-1",
    "sa-east-1",
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
]

# Detailed information about each region's smallest suitable instance
REGION_DETAILS = {
    "eu-south-1": {
        "instance_type": "t3a.small",
        "vcpus": 2,
        "memory_gib": 2.0,
        "spot_price": 0.005300,
    },
    "eu-north-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.005600,
    },
    "ap-southeast-4": {
        "instance_type": "t4g.small",
        "vcpus": 2,
        "memory_gib": 2.0,
        "spot_price": 0.006600,
    },
    "me-central-1": {
        "instance_type": "t4g.small",
        "vcpus": 2,
        "memory_gib": 2.0,
        "spot_price": 0.007300,
    },
    "ap-southeast-3": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.007700,
    },
    "ca-west-1": {
        "instance_type": "t4g.small",
        "vcpus": 2,
        "memory_gib": 2.0,
        "spot_price": 0.007800,
    },
    "ap-south-2": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.008500,
    },
    "sa-east-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.008600,
    },
    "ap-south-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.010700,
    },
    "me-south-1": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.013300,
    },
    "us-west-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.013500,
    },
    "eu-south-2": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.013800,
    },
    "af-south-1": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.014100,
    },
    "eu-central-2": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.014200,
    },
    "ap-east-1": {
        "instance_type": "t3.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.014900,
    },
    "ap-northeast-2": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.016200,
    },
    "eu-west-2": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.017000,
    },
    "ap-southeast-5": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.018600,
    },
    "ap-southeast-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.018700,
    },
    "ca-central-1": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.018900,
    },
    "ap-southeast-2": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.020900,
    },
    "ap-northeast-3": {
        "instance_type": "t4g.medium",
        "vcpus": 2,
        "memory_gib": 4.0,
        "spot_price": 0.021000,
    },
    "eu-west-3": {
        "instance_type": "m6gd.medium",
        "vcpus": 1,
        "memory_gib": 4.0,
        "spot_price": 0.026300,
    },
    "ap-northeast-1": {
        "instance_type": "m5dn.large",
        "vcpus": 2,
        "memory_gib": 8.0,
        "spot_price": 0.058900,
    },
    "eu-central-1": {
        "instance_type": "m6gd.xlarge",
        "vcpus": 4,
        "memory_gib": 16.0,
        "spot_price": 0.065300,
    },
    "us-west-2": {
        "instance_type": "m5d.xlarge",
        "vcpus": 4,
        "memory_gib": 16.0,
        "spot_price": 0.070700,
    },
    "us-east-2": {
        "instance_type": "m5d.xlarge",
        "vcpus": 4,
        "memory_gib": 16.0,
        "spot_price": 0.073000,
    },
    "eu-west-1": {
        "instance_type": "m6gd.xlarge",
        "vcpus": 4,
        "memory_gib": 16.0,
        "spot_price": 0.093600,
    },
    "us-east-1": {
        "instance_type": "t2.2xlarge",
        "vcpus": 8,
        "memory_gib": 32.0,
        "spot_price": 0.107100,
    },
}
