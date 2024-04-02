import argparse
import math
import pprint

import av
import numpy as np
import supervision as sv
from scipy import ndimage
from tqdm import tqdm
from ultralytics import YOLO

model = YOLO("yolov8x.pt")
tracker = sv.ByteTrack()
box_annotator = sv.BoundingBoxAnnotator()


def callback(frame: np.array, _: int) -> np.ndarray:
    results = model(frame)[0]
    detections = sv.Detections.from_ultralytics(results)
    detections = tracker.update_with_detections(detections)
    return box_annotator.annotate(frame.copy(), detections=detections)


def read_video_pyav(container, indices):
    """
    Decode the video with PyAV decoder.
    Args:
        container (`av.container.input.InputContainer`): PyAV container.
        indices (`List[int]`): List of frame indices to decode.
    Returns:
        result (np.ndarray): np array of decoded frames of shape (num_frames, height, width, 3).
    """
    frames = []
    container.seek(0)
    start_index = indices[0]
    end_index = indices[-1]
    for i, frame in enumerate(container.decode(video=0)):
        if i > end_index:
            break
        if i >= start_index and i in indices:
            frames.append(frame)

    return np.stack([x.to_ndarray(format="rgb24") for x in frames])


def sample_frame_indices(
    clip_len_in_seconds, frame_rate, start_idx, seg_len
) -> np.ndarray:
    """
    Sample a given number of frame indices from the video.
    Args:
        clip_len (`int`): Total number of frames to sample.
        frame_sample_rate (`int`): Sample every n-th frame.
        seg_len (`int`): Maximum allowed index of sample's last frame.
    Returns:
        indices (`List[int]`): List of sampled frame indices
    """
    converted_len = clip_len_in_seconds * frame_rate
    end_idx = min(start_idx + converted_len, seg_len)
    indices = np.linspace(start_idx, end_idx, num=converted_len)
    indices = np.clip(indices, start_idx, end_idx - 1).astype(np.int64)
    return indices


# video clip consists of 300 frames (10 seconds at 30 FPS)
# Should be 5 minutes 52s = 352s * 30 FPS = 10560 frames
# 412s * 30 FPS = 12360 frames
videodata = av.open("example_video/IMG_4115.MOV")
frame_rate = math.ceil(
    videodata.streams.video[0].average_rate.numerator
    / videodata.streams.video[0].average_rate.denominator
)


class Detection:
    def __init__(self, confidence, class_id, tracker_id, frame_number):
        self.confidence = confidence
        self.class_id = class_id
        self.tracker_id = tracker_id
        self.count = 1
        self.first_frame = frame_number
        self.last_frame = frame_number

    def increment(self, frame_number):
        self.count += 1
        self.last_frame = frame_number


class FrameTracker:
    tracker = sv.ByteTrack()
    detections = list()

    def __init__(self):
        self.frame_count = 0

    def callback(self, frame: np.ndarray, _: int):
        results = model(frame, verbose=False)[0]
        self.detections = sv.Detections.from_ultralytics(results)
        self.detections = tracker.update_with_detections(self.detections)
        for _, _, confidence, class_id, tracker_id, _ in self.detections:
            print(
                f"Confidence: {confidence}, Class ID: {class_id}, Tracker ID: {tracker_id}"
            )


def compress_video(raw_frames: np.ndarray) -> np.array:
    def rgb2gray(rgb):
        return np.dot(rgb[..., :3], [0.299, 0.587, 0.114])

    ds_frames = ndimage.zoom(raw_frames, (1.0, 0.2, 0.2, 1.0))
    ds_frames = rgb2gray(ds_frames)
    print("downsampled shape =\t", ds_frames.shape)
    print("downsampled frames stored to frames_data.npy")
    return ds_frames


def process_video(
    source_weights_path: str,
    source_video_path: str,
    target_video_path: str,
    confidence_threshold: float = 0.3,
    iou_threshold: float = 0.7,
    skip_frames: int = 1,
) -> None:
    model = YOLO(source_weights_path)  # Load YOLO model

    # LINE_STARTS = sv.Point(0, 500)  # Line start point for count in/out vehicle
    # LINE_END = sv.Point(1280, 500)  # Line end point for count in/out vehicle
    tracker = sv.ByteTrack()  # Bytetracker instance
    # box_annotator = sv.BoundingBoxAnnotator()  # BondingBox annotator instance
    # label_annotator = sv.LabelAnnotator()  # Label annotator instance
    total_frames = 1000
    frame_generator = sv.get_video_frames_generator(
        source_path=source_video_path,
        end=total_frames,
    )  # for generating frames from video
    # video_info = sv.VideoInfo.from_video_path(video_path=source_video_path)
    # line_counter = sv.LineZone(start=LINE_STARTS, end=LINE_END)
    # line_annotator = sv.LineZoneAnnotator(thickness=2, text_thickness=2, text_scale=0.5)

    # 29 total detections
    # Could be more if trucks and cars are detected

    total_detections = {}

    # with sv.VideoSink(target_path=target_video_path, video_info=video_info) as sink:
    for i, frame in enumerate(tqdm(frame_generator, total=total_frames)):
        if skip_frames > 1:
            if i % skip_frames != 0:
                continue

        # Getting result from model
        results = model(
            frame, verbose=False, conf=confidence_threshold, iou=iou_threshold
        )[0]
        detections = sv.Detections.from_ultralytics(results)  # Getting detections
        # Filtering classes for car and truck only instead of all COCO classes.
        detections = detections[
            np.where((detections.class_id == 2) | (detections.class_id == 7))
        ]
        detections = tracker.update_with_detections(
            detections
        )  # Updating detection to Bytetracker
        # Annotating detection boxes
        # annotated_frame = box_annotator.annotate(
        #     scene=frame.copy(), detections=detections
        # )

        # Prepare labels
        # labels = []
        for index in range(len(detections.class_id)):
            if detections.tracker_id[index] not in total_detections:
                total_detections[detections.tracker_id[index]] = Detection(
                    confidence=str(round(detections.confidence[index])),
                    class_id=detections.class_id[index],
                    tracker_id=detections.tracker_id[index],
                    frame_number=i,
                )
            else:
                total_detections[detections.tracker_id[index]].increment(i)
            # creating labels as per required.
            # labels.append(
            #     "#"
            #     + str(detections.tracker_id[index])
            #     + " "
            #     + classes[detections.class_id[index]]
            #     + " "
            #     + str(round(detections.confidence[index], 2))
            # )

            # Line counter in/out trigger
            # line_counter.trigger(detections=detections)
            # Annotating labels
            # label_annotated_frame = label_annotator.annotate(
            #     scene=annotated_frame, detections=detections, labels=labels
            # )
            # sink.write_frame(frame=label_annotated_frame)
            # # Annotating line labels
            # line_annotate_frame = line_annotator.annotate(
            #     frame=annotated_label_frame, line_counter=line_counter
            # )
            # sink.write_frame(frame=line_annotate_frame)


def runner():
    probs = []

    # Sample video every 1 second (30 frames)
    number_of_total_frames = videodata.streams.video[0].frames
    seconds_of_video_in_clip = 10

    classes = [
        "person",
        "bicycle",
        "car",
        "motorbike",
        "aeroplane",
        "bus",
        "train",
        "truck",
        "boat",
        "traffic light",
        "fire hydrant",
        "stop sign",
        "parking meter",
        "bench",
        "bird",
        "cat",
        "dog",
        "horse",
        "sheep",
        "cow",
        "elephant",
        "bear",
        "zebra",
        "giraffe",
        "backpack",
        "umbrella",
        "handbag",
        "tie",
        "suitcase",
        "frisbee",
        "skis",
        "snowboard",
        "sports ball",
        "kite",
        "baseball bat",
        "baseball glove",
        "skateboard",
        "surfboard",
        "tennis racket",
        "bottle",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "hot dog",
        "pizza",
        "donut",
        "cake",
        "chair",
        "sofa",
        "pottedplant",
        "bed",
        "diningtable",
        "toilet",
        "tvmonitor",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        "book",
        "clock",
        "vase",
        "scissors",
        "teddy bear",
        "hair drier",
        "toothbrush",
    ]

    print(f"Frame rate: {frame_rate}")
    for i in range(0, number_of_total_frames, 30):
        frame_tracker = FrameTracker()

        indices = sample_frame_indices(
            clip_len_in_seconds=seconds_of_video_in_clip,
            frame_rate=frame_rate,
            start_idx=i,
            seg_len=videodata.streams.video[0].frames,
        )
        video_frames = read_video_pyav(videodata, indices)

        for frame in video_frames:
            frame_tracker.callback(frame, 0)

        detections = frame_tracker.detections

        pprint.pprint(detections)

        if i % 30 == 0:
            print(f"Processed {i * 30} frames")

        if i >= 60:
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser("video processing with YOLO and ByteTrack")
    parser.add_argument(
        "--source_weights_path",
        required=True,
        help="Path to the source weights file",
        type=str,
    )
    parser.add_argument(
        "--source_video_path",
        required=True,
        help="Path to the source video file",
        type=str,
    )
    parser.add_argument(
        "--target_video_path",
        required=True,
        help="Path to the target video file",
        type=str,
    )
    parser.add_argument(
        "--confidence_threshold",
        default=0.3,
        help="Confidence threshold for the model",
        type=float,
    )
    parser.add_argument(
        "--iou_threshold", default=0.7, help="Iou threshold for the model", type=float
    )

    parser.add_argument(
        "--skip_frames", default=1, help="Only process every n-th frame", type=int
    )
    args = parser.parse_args()
    process_video(
        source_weights_path=args.source_weights_path,
        source_video_path=args.source_video_path,
        target_video_path=args.target_video_path,
        confidence_threshold=args.confidence_threshold,
        iou_threshold=args.iou_threshold,
        skip_frames=args.skip_frames,
    )
