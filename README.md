# Bacalhau Code Examples

This is a collection of worked code examples that use Bacalhau.
For ease of access, they are rendered in the docs at https://docs.bacalhau.org/examples/

* [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau)
* [Documentation](https://docs.bacalhau.org/)
* [Bacalhau Website](https://www.bacalhau.org/)

## Developer Guide

### Ways of Working

All example ideas are tracked as issues in the [Bacalhau Core Repository]() with a label of `example`. 

* If you have an idea for an example, please add an issue.
* If you'd like to work on a example, please find an issue that has not been assigned, then assign the issue to yourself.
* David and Luke will prioritize the examples that are most useful to the community.

### Basic Example

Please see the [basic-template example](templates/basic-template) for a guide on how to create a new example.

### Requirements

* All examples must be ipynb files
* Examples must be placed in "task specific" directories in this repository - this structure is mirrored to the documentation site
* The `todo` and `templates` folder will not be rendered
* Any file named `README.ipynb` or `index.ipynb` will be rendered as the index page for the directory

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

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

### Documentation Testing

All ipynb files (except those in the todo directory) are tested [by a Github action](.github/workflows/test.yaml) using `pytest` and [`nbmake`](https://github.com/treebeardtech/nbmake).

Please try to keep cell execution time to a minimum.

You can [ignore cells](https://github.com/treebeardtech/nbmake#ignore-a-code-cell), [allow exceptions](https://github.com/treebeardtech/nbmake#allow-a-cell-to-throw-an-exception), and more, by adding tags to that cell.

### Developer Help

If you have any questions or spot anything missing, please reach out to `philwinder` or `enricorotundo` on the [Filecoin slack](https://filecoinproject.slack.com/archives/C02RLM3JHUY).
