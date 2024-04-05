# import required libraries
import asyncio

import cv2
import uvicorn
from vidgear.gears.asyncio import WebGear
from vidgear.gears.asyncio.helper import reducer

# various performance tweaks
options = {
    "frame_size_reduction": 40,
    "jpeg_compression_quality": 80,
    "jpeg_compression_fastdct": True,
    "jpeg_compression_fastupsample": False,
}

# initialize WebGear app
web = WebGear(logging=True, **options)


async def frame_producer():
    video_file = "example_video/IMG_9305.MOV"
    stream = cv2.VideoCapture(video_file)
    # loop over frames
    while True:
        # read frame from provided source
        (grabbed, frame) = stream.read()
        # break if NoneType
        if not grabbed:
            # If not grabbed, assume we're at the end, and start over
            stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
            (grabbed, frame) = stream.read()

        # reducer frames size if you want more performance otherwise comment this line
        frame = await reducer(frame, percentage=80)  # reduce frame by 30%
        # handle JPEG encoding
        encodedImage = cv2.imencode(".jpg", frame)[1].tobytes()
        # yield frame in byte format
        yield (
            b"--frame\r\nContent-Type:video/jpeg2000\r\n\r\n" + encodedImage + b"\r\n"
        )
        await asyncio.sleep(0.00001)
    # close stream
    stream.release()


# add your custom frame producer to config
web.config["generator"] = frame_producer

# run this app on Uvicorn server at address http://localhost:8000/
uvicorn.run(web(), host="0.0.0.0", port=8000)

# close app safely
web.shutdown()
