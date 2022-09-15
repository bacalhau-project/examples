# Bacalhau Code Examples

This is a collection of worked code examples that use Bacalhau.
For ease of access they are rendered in the docs at https://docs.bacalhau.org/examples/

* [Bacalhau Core Repository](https://github.com/filecoin-project/bacalhau)
* [Documentation](https://docs.bacalhau.org/)
* [Bacalhau Website](https://www.bacalhau.org/)

## Developer Guide

### Requirements

* All examples must be ipynb files
* Examples must be placed in "task specific" directories in this repository - this structure is mirrored to the documentation site
* The todo folder will not be rendered
* Any file named `README.ipynb` or `index.ipynb` will be rendered as the index page for the directory

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

:warning: Please note that the push of the rendered code will delete and replace the existing files in the docs/examples directory in the [repository](https://github.com/bacalhau-project/docs.bacalhau.org). :warning: 

You can pass Docusaurus yaml metadata by specifying a raw cell at the top of your notebook. See [the index](index.ipynb) for an example.

### Developer Help

If you have any questions or spot anything missing, please reach out to `philwinder` or `enricorotundo` on the [Filecoin slack](https://filecoinproject.slack.com/archives/C02RLM3JHUY).
