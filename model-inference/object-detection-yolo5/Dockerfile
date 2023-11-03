# v7.0
FROM ultralytics/yolov5@sha256:e21b0e965dedac95aac3c6d6d38e2ee26695e1a0cef79d0b746b3fa9bae4f7c6

RUN mkdir /model
ADD https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.pt /model

ENTRYPOINT [ "python", "detect.py", "--weights","/model/yolov5s.pt", "--source","/videos","--project","/outputs","--class","1","2","3","4","5","6","7","9","10","11","12","--save-crop","--conf-thres=.7" ]