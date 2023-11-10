import os

from pydantic import BaseModel


class PublisherConfig(BaseModel):
    bucket: str

class Config(BaseModel):
    host: str
    port: int
    image: str
    publisher: PublisherConfig


def load(file):
    import yaml

    cfg_dict = yaml.safe_load(file)
    cfg = Config(**cfg_dict)

    os.environ["BACALHAU_API_HOST"] = cfg.host
    os.environ["BACALHAU_API_PORT"] = str(cfg.port)
    return cfg
