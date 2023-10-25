import os
from pathlib import Path

from pydantic import BaseModel


class Config(BaseModel):
    questions: str
    answers: str
    timeout: int


def load(file):
    import yaml

    cfg_dict = yaml.safe_load(file)
    cfg = Config(**cfg_dict)

    qpath = Path(cfg.questions).absolute()
    qpath.touch()
    cfg.questions = str(qpath)

    apath = Path(cfg.answers).absolute()
    apath.touch()
    cfg.answers = str(apath)

    return cfg
