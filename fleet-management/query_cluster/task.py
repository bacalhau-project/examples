from argparse import Namespace
from collections import defaultdict
from pprint import pprint
import shutil
import time

from .config import Config
from .util import download_data, merge_files

from pydotdict import DotDict

from bacalhau_apiclient.models.spec import Spec
from bacalhau_apiclient.models.deal import Deal
from bacalhau_apiclient.models.label_selector_requirement import (
    LabelSelectorRequirement,
)
from bacalhau_apiclient.models.job_spec_docker import JobSpecDocker
from bacalhau_apiclient.models.publisher_spec import PublisherSpec
from bacalhau_apiclient.models.storage_spec import StorageSpec

from bacalhau_sdk.api import submit, states
from bacalhau_sdk.config import get_client_id


def run(config: Config, args: Namespace):
    if len(args.query) == 0:
        print("No query provided")
        return

    query = args.query.pop()

    jobspec = dict(
        APIVersion="V1beta2",
        ClientID=get_client_id(),
        Spec=Spec(
            engine="Docker",
            verifier="Noop",
            publisher_spec=PublisherSpec(
                type="S3",
                params={
                    "bucket": config.publisher.bucket,
                    "key": "run-{date}/{jobID}/{nodeID}",
                },
            ),
            docker=JobSpecDocker(
                image=config.image,
                entrypoint=["osqueryi", "--connect=/var/osquery/osquery.em", "--json", query],
            ),
            timeout=1800,
            inputs=[
                StorageSpec(
                    storage_source="localDirectory",
                    name=f"file:///var/osquery/osquery.em",
                    source_path=f"/var/osquery/osquery.em",
                    path=f"/var/osquery/osquery.em",
                )
            ],
            deal={
                "Concurrency": 0,
                "TargetingMode": True,
            },
        ),
    )

    if args.select:
        jobspec["Spec"].node_selectors = parse_selectors(args.select)

    res = DotDict(submit(jobspec).to_dict())
    id = res.job.metadata.id
    print(f"Submitted job: {id}")

    # Describe the job
    res = DotDict(dict(state={"state": "New"}))
    while res.state.state == "New" or res.state.state == "InProgress":
        res = DotDict(states(id).to_dict())
        time.sleep(1)

    output_files = [output_file(**e.published_results.s3) for e in res.state.executions]
    temp_folder = download_data(output_files)

    out_file = f"output-{id[0:8]}.json"
    if args.print:
        merge_files(temp_folder, None)
    else:
        merge_files(temp_folder, out_file)
        print(f"Output written to: {out_file}")

    shutil.rmtree(temp_folder)


def parse_selectors(select: str) -> [LabelSelectorRequirement]:
    """
    Parse a comma separated list of selectors (a=b) and generate a list of
    LabelSelectorRequirements for use in the job spec.

    > parse_selectors("a=b")
    [
        LabelSelectorRequirement(key="a", operator="in", values=["b"])
    ]

    > parse_selectors("a=b,a=c")
    [
        LabelSelectorRequirement(key="a", operator="in", values=["b","c"])
    ]

    """
    selectors = defaultdict(list)
    requirements = []

    for pair in select.split(","):
        k, v = pair.split("=")
        selectors[k].append(v)

    for k, v in selectors.items():
        requirements.append(LabelSelectorRequirement(key=k, operator="in", values=v))

    return requirements


def output_file(*, bucket: str, key: str, **rest) -> (str, str):
    return (bucket, f"{key}stdout")
