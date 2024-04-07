import datetime
import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic_settings import BaseSettings

import random

class Settings(BaseSettings):
    WEB_PORT: int = 8000
    NUMBER_OF_SECONDS_PER_CLIP: int = 10
    FPS: int = 30
    ml_model_config: dict = {}
    ml_model_config_path: str = "config.yaml"
    model: any = None
    tracker: any = None
    total_detections: dict = {}
    working_detections: dict = {}
    # Get datetime of last update for config.yaml
    config_last_update: datetime.datetime = datetime.datetime.now()
    frames_processed_per_clip: int = 0
    model_last_processed_time: datetime.datetime = datetime.datetime.now()

    def load_model(self, model):
        self.model = model

    def load_model_config(self, model_config_path=None):
        if model_config_path is not None:
            self.ml_model_config_path = model_config_path
        model_config_text = Path(self.ml_model_config_path).read_text()
        self.ml_model_config = yaml.safe_load(model_config_text)
        if self.ml_model_config.get("source_video_path") is None:
            # If source_video_path is not set, set it to a random video from the /videos folder
            self.ml_model_config["source_video_path"] = f"videos/{random.choice(os.listdir('videos'))}"
            
        print(f"Model config loaded from {self.ml_model_config}")

    def update_model_config(self, model_config):
        self.ml_model_config = model_config
        self.config_last_update = datetime.datetime.now()

    def update_tracker(self, tracker):
        self.tracker = tracker

    def checkpoint_total_detections(self):
        self.total_detections = self.working_detections
        self.model_last_processed_time = datetime.datetime.now()
        self.working_detections = {}

    def get_model_config_path(self):
        return self.ml_model_config_path


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    if "ml_model_config" not in s or not s.ml_model_config:
        s.load_model_config()
    return s
