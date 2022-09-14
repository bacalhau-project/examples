# Bacalhau Code Examples

A collection of worked examples that use Bacalhau.

> ⚠️ This repe is WIP, soon will be reviewed & updated. In the meantime, please take a look at the [Hello World](https://docs.bacalhau.org/getting-started/installation) and [Image Processing](https://docs.bacalhau.org/demos/image-processing) examples.

* [Bacalhau Website](https://www.bacalhau.org/)
* [Bacalhau Core Code Repository](https://github.com/filecoin-project/bacalhau)
* [Documentation](https://docs.bacalhau.org/)
* [Twitter](https://twitter.com/BacalhauProject)
* [YouTube Channel](https://www.youtube.com/channel/UC45IQagLzNR3wdNCUn4vi0A)

## Developer Guide

### Requirements

* All examples must be ipynb files
* Examples must be placed in "task specific" directories in this repository - this structure is mirrored to the documentation site
* The todo folder will not be rendered
* Due to a bug in docusaurus, files named `index.ipynb` or `README.ipynb` will not be rendered. See [this issue for a fix]. Name your notebooks something like `${task}-${subtask}.ipynb` instead, like the current examples.

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

### Developer Help

If you have any questions or spot anything missing, please reach out to `philwinder` or `enricorotundo` on the filecoin slack.