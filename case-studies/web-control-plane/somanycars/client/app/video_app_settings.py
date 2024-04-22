import datetime
import os
from functools import lru_cache
from pathlib import Path

import yaml
import sqlite3
import random
import jsonpickle
import threading

import logging

from supervision import ByteTrack

import glob
lock = threading.Lock()
DB_PATH = Path("settings.db")
logger = logging.getLogger(__name__)
            
class Settings:
    working_detections = {}
    total_detections = {}
    
    default_dict = {
        "WEB_PORT": 14041,
        "FPS": 30,
        "ml_model_config": {},
        "ml_model_config_path": Path(__file__).parent / "config" / "ml-model-config.yaml",
        "node_config_path": Path(__file__).parent / "config" / "node-config.yaml",
        "model": None,
        "tracker": None,
        "total_detections": {},
        "working_detections": {},
        "config_last_update": datetime.datetime.now(),
        "frames_processed_per_clip": 0,
        "last_inference_time": datetime.datetime.now(),
        "model_running": None,
        "continue_stream": True,
    }
    
    def __init__(self):
        self.ensure_db_setup()
        self.populate_default_settings_if_empty()

    def ensure_db_setup(self):
        # Ensure the database and settings table exist.
        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
            )
            conn.commit()

    def populate_default_settings_if_empty(self):
        # Populate the settings table with default values if it's empty.
        with sqlite3.connect(str(DB_PATH)) as conn:
            if not conn.execute("SELECT * FROM settings").fetchone():
                for key, value in self.default_dict.items():
                    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, jsonpickle.dumps(value)))
                conn.commit()
                
    def delete_db(self):
        if DB_PATH.exists():
            DB_PATH.unlink()
    
    def key_exists(self, key):
        """Synchronously check if a key exists in the cache and has a meaningful value."""
        pickled_value = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if pickled_value:
            value = jsonpickle.loads(pickled_value[0])
            if value is not None:
                if isinstance(value, (str, list, dict)):
                    return bool(value)  # This will return False for empty string/list/dict
                return True
        return False
    
    def execute(self, sql, params):
        try:
            lock.acquire(True)
            logger.debug(f"Executing SQL: {sql} with params: {params}")
            with sqlite3.connect(DB_PATH, timeout=60) as conn:
                cursor = conn.cursor()
                val = cursor.execute(sql, params)
                conn.commit()
                return val
        finally:
            lock.release()
        
    def set(self, key, value):
        if not self.get_continue_stream():
            return
        # Upsert the value into the database, even if the key doesn't exist
        self.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, jsonpickle.dumps(value)))

    def get(self, key):
        json_pickled_value = self.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        value = jsonpickle.loads(json_pickled_value[0]) if json_pickled_value else None
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
            logger.info(f"No custom model config path found, loading model config from {ml_model_config_path}")
            
        ml_model_config = self.get("ml_model_config")
        model_config_text = ml_model_config_path.read_text()
        ml_model_config.update(yaml.safe_load(model_config_text))
        
        if "source_video_path" not in ml_model_config:
            if "source_all_videos_path" not in ml_model_config:
                source_all_videos_path = Path(__file__).parent / "videos"
                logger.info(f"No all videos path found, using {source_all_videos_path}")
                ml_model_config["source_all_videos_path"] = source_all_videos_path

            # Get all videos in the /videos folder - doing this glob excludes hidden
            all_videos = glob.glob(os.path.join(source_all_videos_path, '*'))

            if not all_videos:
                logger.error(f"No videos found in {source_all_videos_path}")
                exit(1)
                return

            # If source_video_path is not set, set it to a random video from the /videos folder
            video_file = random.choice(all_videos)
            ml_model_config["source_video_path"] = video_file
            
            logger.info(f"No video found, using {ml_model_config['source_video_path']}")

        self.set("ml_model_config", ml_model_config)
        logger.info(f"Model config loaded from {ml_model_config_path}")
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
        self.set("total_detections", self.working_detections)
        self.set("last_inference_time", datetime.datetime.now())
        self.working_detections = {}

    def get_model_config_path(self) -> Path:
        return self.get("ml_model_config_path")

    def set_model_running(self, running = datetime.datetime.now()):
        logger.info(f"Set model running - {format(running)}")
        self.set("model_running", running)

    def set_model_stopped(self):
        logger.info(f"Set model stopped - {format(datetime.datetime.now())} (was running at {self.get('model_running')})")
        self.set("model_running", None)

    def is_model_running(self) -> bool:
        return self.get("model_running")

    def start_stream(self):
        self.set("continue_stream", True)
        
    def stop_stream(self):
        self.set("continue_stream", False)

    def get_continue_stream(self):
        return self.get("continue_stream")

    def toggle_continue_stream(self):
        self.set("continue_stream", not self.get("continue_stream"))

@lru_cache()
def get_settings() -> Settings:
    s = Settings()
    return s

