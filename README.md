# Bacalhau Code Examples

This is a collection of worked code examples that use Bacalhau.
For ease of access, they are rendered in the docs at https://docs.bacalhau.org/examples/

* [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau)
* [Documentation](https://docs.bacalhau.org/)
* [Bacalhau Website](https://www.bacalhau.org/)

## Developer Guide

### Before You Start

All example ideas are tracked as issues in the [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau/issues?q=is%3Aopen+is%3Aissue+label%3Aexample) with a label of `example`. 

* If you have an idea for an example, please add an issue.
* If you'd like to work on a example, please find an issue that has not been assigned, then assign the issue to yourself.
* David and Luke will prioritize the examples that are most useful to the community.

### General Process

In summary, the process of developing an example is as follows:

1. Create a new branch and create an `index.ipynb` file in an appropriate directory.
2. Develop the notebook and make sure `make test path/to/your/notebook.ipynb` passes
3. Merge into master
4. The CI will then render the notebook and push it to the [docs.bacalhau.org repository](https://github.com/bacalhau-project/docs.bacalhau.org/)
5. The tests run on a cron basis to ensure examples continue to work 

### Example Template

Please see the [basic-template example](templates/basic-template) for a guide on how to create a new example.

### Requirements

The following guidelines aim to maintain the quality of the examples.

#### Example Requirements

* The example should be useful, try to avoid toy datasets
* Don't repeat yourself, if there is an example of something already available, redirect to that. For example, don't show people how to ingest data into IPFS, there's [an example for that](data-ingestion).

#### Markdown Requirements

* The text should be in English and be free of grammatical mistakes.
* Use good headings and (probably) use numbered top-level headings to show significantly different sections or steps. Use your judgement.
* Remove all formatting other than standard markdown. Examples include rogue page breaks, extra bold formatting in headings (`**`), quotation marks around monospaced code, etc.

#### Dependency Requirements

* If you have prerequisites, place these at the top of the file just after the introduction at a third level heading (`###`).
* If you install anything, use a tagged version. Examples include Docker containers, `pip` installs. Etc.

#### Notebook Requirements

* All examples must be ipynb files
* Any file named `README.ipynb` or `index.ipynb` will be rendered as the index page for the directory (see the current examples and the docs website)
* Prefer fewer cells, they are easier to edit.
* No spaces in directory names
* Every rendered directory requires an index.ipynb file, so the HTML index.html file is not empty.
* All rendered notebooks must have the required Docusaurus YAML at the top of the file (see the current examples and templates)
* Try to avoid using HTML in markdown, it will likely break. If you need to, use IPython's HTML class and hide the code cell.

#### Testing Requirements

* Make sure `make convert` and `make test` succeeds and runs in a reasonable time.
* Only commit to the examples repo, the CI will take care of committing to the docs site.

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown, test it, and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

#### Manually Rendering Docs

If you want to render your docs locally, then run `make convert`. You can also look at the [CI script](.github/workflows/publish.yaml) to see the setup.

#### Testing Docs.Bacalhau.Org

To test whether your rendered docs will work on the docs site, run `make docs`.

This code is slightly different to the test in the CI, but achieves the same result.

#### Removing Cells From the Rendered Markdown

[Cells can be ignored](https://github.com/treebeardtech/nbmake#ignore-a-code-cell) (or inputs -- remove_input, or outputs -- remove_output) by adding the following to the cell metadata:

```json
...
    "metadata": {
        "tags": [
            "remove_cell"
        ]
    },
...
```

:warning: Please note that the push of the rendered code will delete and replace the existing files in the docs/examples directory in the [repository](https://github.com/bacalhau-project/docs.bacalhau.org). :warning: 

#### Docusaurus Metadata

The top most cell of every notebook **must** have a raw cell with a bit of yaml in it:

```yaml
---
sidebar_label: "Basic Template"
sidebar_position: 1
---
```

* `sidebar_label` is the label shown in the Docusaurus sidebar
* `sidebar_position` sets the ordering of the labels in the sidebar. Lower values appear at the top.

See [the template](templates/basic-template/index.ipynb) for an example.

Depending on what editor you are using, you might need to open the file in raw "text" mode to see it. It looks something like this:

```json
...
  {
   "cell_type": "raw",
   "metadata": {},
   "source": [
    "---\n",
    "sidebar_label: \"Basic Template\"\n",
    "sidebar_position: 1\n",
    "---"
   ]
  },
...
```

### Documentation Testing

All ipynb files (except those in the todo directory) are tested [by a Github action](.github/workflows/test.yaml) using `pytest` and [`nbmake`](https://github.com/treebeardtech/nbmake).

Please try to keep cell execution time to a minimum.

You can [ignore cells](https://github.com/treebeardtech/nbmake#ignore-a-code-cell), [allow exceptions](https://github.com/treebeardtech/nbmake#allow-a-cell-to-throw-an-exception), and more, by adding tags to that cell.

#### Manually Testing

You can run test all notebooks with `make test`. If you want to test an individual notebook, you can run something like `make test miscellaneous/Gromacs/index.ipynb`.

### Developer Help

If you have any questions or spot anything missing, please reach out to `philwinder` or `enricorotundo` on the #bacalhau channel in [Filecoin Slack](https://filecoin.io/slack).
# Bacalhau Job Queueing Demo

This repository demonstrates how to use Bacalhau to perform job queueing. The setup will create four nodes on Azure, with public keys, and ensure the nodes can communicate with each other.

## Prerequisites

- Azure account
- Terraform installed
- SSH keys generated

## Setup

1. Clone the repository:
    ```sh
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Initialize Terraform:
    ```sh
    terraform init
    ```

3. Apply the Terraform configuration to create the nodes:
    ```sh
    terraform apply
    ```

4. Ensure the nodes can communicate with each other by exchanging public keys.

## Usage

- Submit jobs to the Bacalhau job queue.
- Monitor the job execution and results.

## Cleanup

To destroy the created resources, run:
```sh
terraform destroy
```

## License

This project is licensed under the MIT License.
