- Download all the model weights using download_all_models.py

----

To run the server, execute the following commands:
```bash
pip install uv # For your global settings
uv venv .venv --seed
uv pip install -r requirements.txt
# Set the environment variables to whatever you want
PORT=14041 HOST=localhost WEIGHTSDIR=app/weights VIDEOSDIR=app/videos ./run serve:local
```

To build the client into a container:
```bash
VERSION=0.0.xxx # Set the version number
echo $VERSION > VERSION # Change the version number in the VERSION file
./run build-and-submit:cloud # You need to have login for our bacalhauproject on docker hub
```

To run test the client locally, with Docker compose;
```bash
./run serve
```