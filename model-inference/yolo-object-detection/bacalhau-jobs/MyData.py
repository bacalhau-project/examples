from aperturedb.Utils import create_connector, Utils
from aperturedb.Subscriptable import Subscriptable
from typer import Typer
import pandas as pd
import os
import json
from datetime import datetime
import subprocess

app = Typer()

class MyData(Subscriptable):
    def __init__(self, path:str =  "/results/exp/"):
        self.all_predictions = {}
        for dpath, dname, filenames in os.walk(path):
            for fname in filenames:
                full_path = os.path.join(dpath, fname)
                if full_path.endswith("json"):
                    with open(full_path) as pred_stream:
                        for prediction in pred_stream.readlines():
                            pred = json.loads(prediction)
                            key = "Image Name"
                            data = {
                                "meta_full_path": full_path,
                            }
                            if pred[key] in self.all_predictions:
                                self.all_predictions[pred[key]]["predictions"].append(pred)
                            else:
                                self.all_predictions[pred[key]] = data
                                self.all_predictions[pred[key]]["predictions"] = [pred]
        print("loaded")


    def __len__(self):
        return len(self.all_predictions)

    def getitem(self, idx):
        keys = list(self.all_predictions.keys())
        key = keys[idx]
        ctx = self.all_predictions[key]

        full_mpeg_path = os.path.join(os.path.dirname(ctx["meta_full_path"]), key)
        dest_path = full_mpeg_path.replace(".mp4", ".h264.mp4")
        if not os.path.exists(dest_path):
            p = subprocess.Popen(
                f"ffmpeg -i '{full_mpeg_path}' -vcodec libx264 -acodec aac '{dest_path}' 1> /dev/null 2>/dev/null", shell=True
            )
            status = p.wait()
        query = [
            {
                "AddVideo": {
                    "if_not_found": {
                        "video_id": ["==", key]
                    },
                    "properties":{
                        "video_id": key,
                        "full_path": dest_path
                    },
                    "_ref": 1
                }
            }
        ]
        predictions = ctx["predictions"]
        for prediction in predictions:
            x, y, w, h = prediction["XYWH"]
            ts = prediction["Timestamp"].split(":")
            cts = datetime.now()
            query.append(
                {
                    "AddEntity": {
                        "class": "VideoBoundingBox",
                        "properties": {
                            "label": prediction["Prediction"],
                            # TODO this needs to be a float.
                            "confidence": prediction["Confidence"],
                            # TODO these probably need to be floats too.
                            "X": x,
                            "Y": y,
                            "W": w,
                            "H": h,
                            # TODO this represents the time in the video at which the object (label) was detected.
                            "ts": {"_date": datetime(
                                year=cts.year,
                                month=cts.month,
                                day=int(ts[0]) + 1,
                                hour=int(ts[1]),
                                minute=int(int(ts[2])),
                                second=int(int(ts[3])),
                                microsecond=int(int(ts[4]))
                            ).isoformat() }
                        },
                        "connect":{
                            "ref": 1,
                            "class": "VideoToVideoBoundingBox"
                        }
                    }
                }
            )
        video_file_path = query[0]["AddVideo"]["properties"]["full_path"]
        blobs = []
        with open(video_file_path, "rb") as instream:
            blobs.append(instream.read())
        assert len(blobs) == 1
        return query, blobs

@app.command()
def main():
    db = create_connector()
    utils = Utils(db)
    utils.summary()

@app.command()
def test_generator(path:str):
    gen = MyData(path=path)
    print(len(gen))
    # print(gen[0])


if __name__ == "__main__":
    app()
