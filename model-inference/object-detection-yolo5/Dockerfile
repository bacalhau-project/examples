# v7.0
# example: docker run -e CLASSES="1 2 3" -e CONF_THRES="0.5"
FROM ultralytics/yolov5@sha256:e21b0e965dedac95aac3c6d6d38e2ee26695e1a0cef79d0b746b3fa9bae4f7c6

# Embed a default model that we may override via env var
RUN mkdir /model
ADD https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.pt /model

# Set default environment variables
ENV CLASSES="1 2 3 4 5 6 7 9 10 11 12"
ENV CONF_THRES="0.7"
ENV WEIGHTS_PATH="/model/yolov5s.pt"

ENTRYPOINT ["sh", "-c", "python detect.py --weights $WEIGHTS_PATH --source /videos --project /outputs --class $CLASSES --save-crop --conf-thres=$CONF_THRES"]
