import datetime
import os
from functools import lru_cache
from pathlib import Path

import yaml
import sqlite3
import random
import jsonpickle

from supervision import ByteTrack

            
class Settings:
    conn = None
    working_detections = {}
    total_detections = {}
    
    default_dict = {
        "WEB_PORT": 14041,
        "NUMBER_OF_SECONDS_PER_CLIP": 10,
        "FPS": 30,
        "ml_model_config": {},
        "ml_model_config_path": Path(__file__).parent / "config" / "model-config.yaml",
        "node_config_path": Path(__file__).parent / "config" / "node-config.yaml",
        "model": None,
        "tracker": None,
        "total_detections": {},
        "working_detections": {},
        "config_last_update": datetime.datetime.now(),
        "frames_processed_per_clip": 0,
        "last_inference_time": datetime.datetime.now(),
    }
    
    def __init__(self):
        # Create a new in-memory database if one doesn't exist
        if not self.conn:
            self.conn = sqlite3.connect(":memory:")
            self.conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
            self.conn.commit()
        
        if not self.conn.execute("SELECT * FROM settings").fetchone():
            for key, value in self.default_dict.items():
                self.conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, jsonpickle.dumps(value)))
            self.conn.commit()

    
    def key_exists(self, key):
        """Synchronously check if a key exists in the cache and has a meaningful value."""
        pickledvalue = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if pickledvalue:
            value = jsonpickle.loads(pickledvalue[0])
            if value is not None:
                if isinstance(value, (str, list, dict)):
                    return bool(value)  # This will return False for empty string/list/dict
                return True
        return False
    
        
    def set(self, key, value):
        self.conn.commit()
        self.conn.execute("UPDATE settings SET value = ? WHERE key = ?", (jsonpickle.dumps(value), key))
    
    def get(self, key):
        jsonpicklevalue = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        value = jsonpickle.loads(jsonpicklevalue[0]) if jsonpicklevalue else None
        return value

    def load_model(self, model):
        self.set("model", model)

    # Function loads the model config from the ml_model_config_path
    # and overwrites the ml_model_config in memory
    def load_model_config(self, ml_model_config_path=None):
        if ml_model_config_path is not None:
            self.set("ml_model_config_path", ml_model_config_path)
        else:
            ml_model_config_path = self.get("ml_model_config_path")
            print(f"No custom model config path found, loading model config from {ml_model_config_path}")
            
        ml_model_config = self.get("ml_model_config")
        model_config_text = ml_model_config_path.read_text()
        ml_model_config.update(yaml.safe_load(model_config_text))
        
        if "source_video_path" not in ml_model_config:
            if "source_all_videos_path" not in ml_model_config:
                source_all_videos_path = Path(__file__).parent / "videos"
                print(f"No all videos path found, using {source_all_videos_path}")
                ml_model_config["source_all_videos_path"] = source_all_videos_path

            # If source_video_path is not set, set it to a random video from the /videos folder
            video_file = random.choice(os.listdir(str(source_all_videos_path.absolute())))
            ml_model_config["source_video_path"] = (
                f"{source_all_videos_path.absolute()}/{video_file}"
            )
            
            print(f"No video found, using {ml_model_config['source_video_path']}")

        self.set("ml_model_config", ml_model_config)
        print(f"Model config loaded from {ml_model_config_path}")
        return ml_model_config

    def update_model_config(self, ml_model_config):
        ml_model_config = self.get("ml_model_config")
        ml_model_config.update(ml_model_config)
        self.set("ml_model_config", ml_model_config)
        self.set("config_last_update", datetime.datetime.now())

    def update_tracker(self, tracker):
        self.set("tracker", tracker)
        
    def update_tracker_with_detections(self, detections) -> ByteTrack:
        tracker = self.get("tracker")
        detections = tracker.update_with_detections(detections)
        self.set("tracker", tracker)
        return detections

    def checkpoint_total_detections(self):
        self.set("total_detections", self.get("working_detections"))
        self.set("last_inference_time", datetime.datetime.now())
        self.set("working_detections", {})

    def get_model_config_path(self) -> Path:
        return self.get("ml_model_config_path")


@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    if s.key_exists("ml_model_config"):
        s.load_model_config()
    return s
