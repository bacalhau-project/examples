# Bacalhau Code Examples

This is a collection of worked code examples that use Bacalhau.
For ease of access, they are rendered in the docs at https://docs.bacalhau.org/examples/

* [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau)
* [Documentation](https://docs.bacalhau.org/)
* [Bacalhau Website](https://www.bacalhau.org/)

## Developer Guide

### Ways of Working

All example ideas are tracked as issues in the [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau/issues?q=is%3Aopen+is%3Aissue+label%3Aexample) with a label of `example`. 

* If you have an idea for an example, please add an issue.
* If you'd like to work on a example, please find an issue that has not been assigned, then assign the issue to yourself.
* David and Luke will prioritize the examples that are most useful to the community.

### Basic Example

Please see the [basic-template example](templates/basic-template) for a guide on how to create a new example.

### Requirements

* All examples must be ipynb files, only ipynb files are rendered to the docs site
* Examples must be placed in "task specific" directories in this repository - this structure is mirrored to the documentation site
* The `todo` and `templates` folder will not be rendered
* Any file named `README.ipynb` or `index.ipynb` will be rendered as the index page for the directory (see the current examples and the docs website)
* Every rendered directory requires an index.ipynb file, so the HTML index.html file is not empty.
* No spaces in directory names
* All rendered notebooks must have the required Docusaurus YAML at the top of the file (see the current examples and templates)
* Try to avoid using HTML in markdown, it will likely break. If you need to, use IPython's HTML class and hide the code cell.
* Make sure `make render` and `make test` succeeds and runs in a reasonable time.
* Only commit to the examples repo, the CI will take care of committing to the docs site.

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

#### Manually Rendering Docs

If you want to render your docs locally, then run `make render`. You can also look at the [CI script](.github/workflows/publish.yaml) to see the setup.

#### Viewing Manually Rendered Docs on a Development Docs.Bacalhau.Org

You can also copy the rendered markdown files across to a local copy of the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/). Assuming you have cloned both the examples and docs repositories into a directory called `~/source`:

```bash
cd ~/source/bacalhau-project/examples
make convert
cd ~/source/filecoin-project/docs.bacalhau.org
cp -r ~/source/bacalhau-project/examples/rendered/. docs/examples/.
yarn start
```

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
