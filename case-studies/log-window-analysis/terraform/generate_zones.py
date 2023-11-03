import subprocess
import json


def get_zones_with_e2():
    zones_with_e2 = {}

    # Get all zones in the region
    zones = json.loads(subprocess.check_output(f"gcloud compute zones list --format=json", shell=True))

    e2_zones = json.loads(
        subprocess.check_output(
            f"gcloud compute machine-types list --filter=NAME=e2-standard-2 --format=json", shell=True
        )
    )

    for zone in zones:
        for e2_zone in e2_zones:
            if zone["name"] == e2_zone["zone"]:
                storageLocation = zone["name"].split("-")[0].upper()
                # if the storage location isn"t US, EU or ASIA, then pick the closest region
                if storageLocation not in ["US", "EU", "ASIA"]:
                    # If "australia", then use "ASIA"
                    if storageLocation == "AUSTRALIA":
                        storageLocation = "ASIA"
                    # If "southamerica", then use "US"
                    elif storageLocation == "SOUTHAMERICA":
                        storageLocation = "US"
                    # If "africa", then use "EU"
                    elif storageLocation == "AFRICA":
                        storageLocation = "EU"
                    # If "me", then use "EU"
                    elif storageLocation == "ME":
                        storageLocation = "EU"

                region = zone["region"].split("/")[-1]

                zones_with_e2[zone["name"]] = {
                    "region": region,
                    "storage_location": storageLocation,
                }

    return zones_with_e2


print(get_zones_with_e2())
