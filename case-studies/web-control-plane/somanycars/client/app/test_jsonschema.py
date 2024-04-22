import jsonschema
import requests

# Curl localhost:14041/schema to get jsonschema
# Then use this to validate the json
def test_validate_json():
    # Get the jsonschema from the server
    schema = requests.get("http://localhost:14041/schema").json()
    
    print(schema)

    
    
test_validate_json()