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
* Any file named `README.ipynb` or `index.ipynb` will be rendered as the index page for the directory

### Documentation Rendering

Whenever you push to the main branch on this repository, a github action will automatically render your ipynb's into markdown and push them to the [docs repository](https://github.com/bacalhau-project/docs.bacalhau.org/).

:warning: Please note that the push of the rendered code will delete and replace the existing files in the docs/examples directory in the [repository](https://github.com/bacalhau-project/docs.bacalhau.org). :warning: 

You can pass Docusaurus yaml metadata by specifying a raw cell at the top of your notebook. See [the index](index.ipynb) for an example.

### Developer Help

If you have any questions or spot anything missing, please reach out to `philwinder` or `enricorotundo` on the filecoin slack.