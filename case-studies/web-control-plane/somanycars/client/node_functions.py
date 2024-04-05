import random


def generateHashCode(str):
    hash_value = 0
    for char in str:
        hash_value = (hash_value << 5) - hash_value + ord(char)

    # Convert hash to a positive integer (assuming hash is signed)
    hash_int = hash_value & 0xFFFFFFFF
    # Convert integer to base 36 string
    base36_string = base36_encode(hash_int)
    # Pad the string to have at least 7 characters with leading zeros
    padded_string = base36_string.zfill(7)
    return padded_string


def base36_encode(integer):
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    base36 = ""
    sign = ""
    if integer < 0:
        sign = "-"
        integer = -integer
    while integer != 0:
        integer, i = divmod(integer, 36)
        base36 = alphabet[i] + base36
    return sign + base36 if sign else base36


def test_node():
    n = random.choice(TEST_NODES_STATICS)
    return {"ip": n[0], "hostname": n[1], "region": n[2], "zone": n[3]}


def generate_node(
    hostname,
    ip,
    model_weights,
    hashCode,
    zone,
    region,
    nodeID,
    video_feed,
    confidence_threshold,
    iou_threshold,
    skip_frames,
    source_video_path,
    total_detections,
    frames_processed_per_clip,
):
    return {
        "hostname": hostname,
        "ip": ip,
        "model_weights": model_weights,
        "hashCode": hashCode,
        "zone": zone,
        "region": region,
        "nodeID": nodeID,
        "video_feed": video_feed,
        "confidence_threshold": confidence_threshold,
        "iou_threshold": iou_threshold,
        "skip_frames": skip_frames,
        "source_video_path": source_video_path,
        "total_detections": total_detections,
        "frames_processed_per_clip": frames_processed_per_clip,
    }


TEST_NODES_STATICS = (
    ["256.256.256.1", "silva-odonnell.net", "us-west1", "us-west1-a"],
    ["256.256.256.2", "campbell.org", "us-west1", "us-west1-a"],
    ["256.256.256.3", "archer-patel.org", "us-west1", "us-west1-b"],
    ["256.256.256.4", "collins.com", "us-west1", "us-west1-b"],
    ["256.256.256.5", "rivera.com", "us-east1", "us-east1-a"],
    ["256.256.256.6", "bowman.info", "us-east1", "us-east1-a"],
    ["256.256.256.7", "green.com", "us-east1", "us-east1-b"],
    ["256.256.256.8", "turner.com", "us-east1", "us-east1-b"],
    ["256.256.256.9", "cortez.com", "eu-west1", "eu-west1-a"],
    ["256.256.256.10", "snyder.com", "eu-west1", "eu-west1-a"],
    ["256.256.256.11", "harrell.com", "eu-west1", "eu-west1-b"],
    ["256.256.256.12", "mclean.net", "eu-west1", "eu-west1-b"],
    # New entries start here
    ["256.256.256.13", "adams-lee.com", "asia-east1", "asia-east1-a"],
    ["256.256.256.14", "baker-co.com", "asia-east1", "asia-east1-a"],
    ["256.256.256.15", "clarkson.org", "asia-east1", "asia-east1-b"],
    ["256.256.256.16", "davies.info", "asia-east1", "asia-east1-b"],
    ["256.256.256.17", "evans.net", "asia-south1", "asia-south1-a"],
    ["256.256.256.18", "floyd.co.uk", "asia-south1", "asia-south1-a"],
    ["256.256.256.19", "gibson.org", "asia-south1", "asia-south1-b"],
    ["256.256.256.20", "harris.com", "asia-south1", "asia-south1-b"],
    ["256.256.256.21", "irwin.net", "eu-north1", "eu-north1-a"],
    ["256.256.256.22", "jones.org", "eu-north1", "eu-north1-a"],
    ["256.256.256.23", "kelly.com", "eu-north1", "eu-north1-b"],
    ["256.256.256.24", "lewis.info", "eu-north1", "eu-north1-b"],
    ["256.256.256.25", "morgan.net", "us-central1", "us-central1-a"],
    ["256.256.256.26", "nelson.org", "us-central1", "us-central1-a"],
    ["256.256.256.27", "owens.com", "us-central1", "us-central1-b"],
    ["256.256.256.28", "patterson.info", "us-central1", "us-central1-b"],
    ["256.256.256.29", "quinn.net", "au-southeast1", "au-southeast1-a"],
    ["256.256.256.30", "reid.org", "au-southeast1", "au-southeast1-a"],
    ["256.256.256.31", "smith.com", "au-southeast1", "au-southeast1-b"],
    ["256.256.256.32", "taylor.info", "au-southeast1", "au-southeast1-b"],
    ["256.256.256.33", "underwood.net", "sa-east1", "sa-east1-a"],
    ["256.256.256.34", "vance.org", "sa-east1", "sa-east1-a"],
    ["256.256.256.35", "williams.com", "sa-east1", "sa-east1-b"],
    ["256.256.256.36", "xavier.info", "sa-east1", "sa-east1-b"],
    ["256.256.256.37", "young.net", "eu-central1", "eu-central1-a"],
    ["256.256.256.38", "zimmerman.org", "eu-central1", "eu-central1-a"],
    ["256.256.256.39", "arnold.com", "eu-central1", "eu-central1-b"],
    ["256.256.256.40", "brooks.info", "eu-central1", "eu-central1-b"],
    ["256.256.256.41", "carter.net", "asia-northeast1", "asia-northeast1-a"],
    ["256.256.256.42", "dunn.org", "asia-northeast1", "asia-northeast1-a"],
    ["256.256.256.43", "elliott.com", "asia-northeast1", "asia-northeast1-b"],
    ["256.256.256.44", "fischer.info", "asia-northeast1", "asia-northeast1-b"],
    ["256.256.256.45", "gray.net", "na-north1", "na-north1-a"],
    ["256.256.256.46", "holt.org", "na-north1", "na-north1-a"],
    ["256.256.256.47", "ingram.com", "na-north1", "na-north1-b"],
    ["256.256.256.48", "jennings.info", "na-north1", "na-north1-b"],
)
