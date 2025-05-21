import os
import json
import cv2
import random
import time
import socket
from datetime import datetime
from ultralytics import YOLO

model_path = "/app/model-node4.pt"
input_dir = "/mnt/local_files/input"
output_base = "/mnt/local_files/output"
low_bandwidth_dir = os.path.join(output_base, "LOW_bandwidth")
high_bandwidth_dir = os.path.join(output_base, "HIGH_bandwidth")
logs_dir = os.path.join(output_base, "logs")

model = YOLO(model_path)

def create_thumbnail(image, size=(256, 256)):
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA)

def current_time():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def process_image(filename):
    image_path = os.path.join(input_dir, filename)
    name_wo_ext = os.path.splitext(filename)[0]
    low_dir = os.path.join(low_bandwidth_dir, name_wo_ext)
    high_dir = os.path.join(high_bandwidth_dir, name_wo_ext)
    log_dir = os.path.join(logs_dir, name_wo_ext)
    log_file = os.path.join(log_dir, "file.log")

    os.makedirs(low_dir, exist_ok=True)
    os.makedirs(high_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    def log(message):
        entry = f"[{current_time()}] {message}"
        print(entry)
        with open(log_file, "a") as f:
            f.write(entry + "\n")

    log(f"Start processing file {filename}")

    image = cv2.imread(image_path)
    if image is None:
        log(f"❌ Failed to read image: {image_path}")
        return

    log("Running YOLO inference...")
    results = model(image)
    detected_classnames = results[0].names
    detections = results[0].obb if hasattr(results[0], 'obb') and results[0].obb is not None else []

    ships = [
        det for det in detections
        if detected_classnames[int(det.cls)] == "ship" and float(det.conf) > 0.6
    ]
    ship_count = len(ships)
    ship_detect = ship_count > 0
    model_info = type(model.model).__name__

    log(f"Detection completed: {ship_count} ships detected. Model used: {model_info}")

    fake_coords = {
        "latitude": round(random.uniform(-90, 90), 6),
        "longitude": round(random.uniform(-180, 180), 6)
    } if ship_detect else None

    output_json = {
        "image": filename,
        "ship_count": ship_count,
        "ship_detect": ship_detect,
        "model_info": model_info,
        "node": os.environ.get("HOSTNAME", socket.gethostname())
    }
    if fake_coords:
        output_json["fake_coordinates"] = fake_coords

    thumbnail = create_thumbnail(image)

    # LOW bandwidth
    log("Saving LOW bandwidth output...")
    cv2.imwrite(os.path.join(low_dir, "thumbnail.jpg"), thumbnail)
    with open(os.path.join(low_dir, "result.json"), "w") as f:
        json.dump(output_json, f, indent=4)

    # HIGH bandwidth
    log("Saving HIGH bandwidth output...")
    annotated = results[0].plot()
    cv2.imwrite(os.path.join(high_dir, "thumbnail.jpg"), thumbnail)
    cv2.imwrite(os.path.join(high_dir, "original.jpg"), image)
    cv2.imwrite(os.path.join(high_dir, "annotated.jpg"), annotated)
    with open(os.path.join(high_dir, "result.json"), "w") as f:
        json.dump(output_json, f, indent=4)

    # Usunięcie pliku wejściowego
    os.remove(image_path)
    log(f"Input file {image_path} removed.")

    log(f"✅ Completed processing of {filename}")

# Główne przetwarzanie
try:
    for filename in os.listdir(input_dir):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
            continue
        process_image(filename)
    print("🎉 All files processed. Exiting.")
except Exception as e:
    print(f"🔥 Error during processing: {e}")
