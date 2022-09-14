# running How to EUREC4A locally

There are multiple options to run the Code examples from this book locally.
In any case, it will involve the following steps:
* install Python (we assume hat this is already done, have a look at [python.org](https://python.org) if you want to get it)
* obtain the code from the book
* install all required dependencies
* run the code

You can decide between the [quick an dirty](#quick-and-dirty) method and the method [using `git`](#via-git), which will also set you up to contribute to the book.

## quick and dirty
If you just like to run the code of a single notebook and don't care to much about the details, the quickest option might be to download the chapter you are viewing as an ipython notebook (`.ipynb`) via the download button (<i class="fas fa-download"></i>) on the top right of the page. If you don't see the `.ipynb` option here, that's because the source of the page can not be interpreted as a notebook and thus is not available for direct execution.

If you would just run the downloaded code, the chance is high that some required libraries are not yet installed on your system. You can either do try and error to find out which libraries are required for the chapter you downloaded, or you can simply installed all requirements for the entire book by running the following command on your command line:
`````{grid} 2
````{grid-item-card} Using pip
```bash
pip install jupyter
pip install -r https://raw.githubusercontent.com/eurec4a/how_to_eurec4a/master/requirements.txt
```
+++
This won't work with any notebooks that use `cartopy` to make maps,  `pip` does not manage
their dependencies well.
````
````{grid-item-card} Using conda
```bash
wget https://raw.githubusercontent.com/eurec4a/how_to_eurec4a/master/requirements.txt
conda create -f requirements.txt
conda activate how_to_eurec4a
```
+++
This creates a conda environment called `how_to_eurec4a` which contains all dependencies including
`cartopy`
````
`````

Afterwards, you can start a local notebook server (either `jupyter notebook` or `jupyter lab`) and run and modify the chapter locally.

```{note}
Handling requirements in this project is not entirely straightforward, as the requirements strongly depend on which datasets are used. We use [intake catalogs](https://intake.readthedocs.io) to describe how a dataset can be accessed which simplifies a lot of things. But as a consequence the set of required libraries is not only determined by the code in this repository, but also by the entries in the catalog.
```

## via git

If you like to do it more properly, you can also clone the repository via git. Depending on if you have SSH public key authentication set up or not, you can do this via SSH or HTTPS:

`````{tab-set}
````{tab-item} SSH
```bash
git clone git@github.com:eurec4a/how_to_eurec4a.git
```
````
````{tab-item} HTTPS
```bash
git clone https://github.com/eurec4a/how_to_eurec4a
```
````
`````
````{admonition} Maybe use a virtual environment
:class: dropdown, tip
If you use pip you might want to use a virtual environment for the book if you like to keep the required libraries in a confined place, but it is entirely optional and up to your preferences.
There are many options to do so and [virtualenv](https://virtualenv.pypa.io/) is one of them.
Using virtualenv, you could create and activate an environment like:
```bash
virtualenv venv
. venv/bin/activate
```
and the continue normally.
````
You'll have to install the dependencies as above, but as you already have all the files on your machine, you can also install it directly via:

`````{grid} 2
````{grid-item-card} Using pip
```bash
pip install jupyter
pip install -r requirements.txt
```
+++
This won't work with any notebooks that use `cartopy` to make maps,  `pip` does not manage
their dependencies well.
````
````{grid-item-card} Using conda
```bash
conda create -f requirements.txt
conda activate how_to_eurec4a
```
+++
This creates a conda environment called `how_to_eurec4a` which contains all dependencies including
`cartopy`
````
`````

Depending on your needs, you can continue using [interactive notebooks](#interactive) or [compile the entire book](#compile-the-book).

```{admonition} About MyST notebooks.
:class: dropdown
Internally, the book does not use the `.ipynb` file format as it is not well-suited for version control.
Instead, we use [Markedly Structured Text](https://myst-parser.readthedocs.io/) or MyST which is a variant of Markdown, optimized to contain executable code cells as in notebooks.
The extension of MyST files is `.md`.
In contrast to notebooks, these files **do not** contain generated cell outputs, so you'll actually have to run the files in order to see anything.

`jupytext` is used to convert between MyST and `ipynb` formats.
It is installed through the `requirements.txt` and should register itself with `jupyter`, so that you can open the files as if they where `ipynb` files.
If that does not work, please have a look at the [installation instructions](https://jupytext.readthedocs.io/en/latest/install.html) of `jupytext`.
```

### interactive
`jupyter` itself is not installed by the requirements file. If you're using `pip` you might want to install it as well:

```bash
pip install jupyter
```

Once everything is set up, you can either start your notebook server:
`````{grid} 2
````{grid-item-card}
... either using classical notebooks
```bash
jupyter notebook
```
````
````{grid-item-card}
... or using jupyter lab
```bash
jupyter lab
```
````
`````

### compile the book
You can also execute `jupyter-book` directly via:
```bash
jb build how_to_eurec4a
```
which itself will run all code cells and output the results as HTML pages in a newly created folder.
This variant is especially useful if you like to work directly on the MyST files (see note below) using a text editor and should be done every time before you submit new changes to the book.

### adding new articles
Articles are generated from markdown files within the `how_to_eurec4a` folder of the git repository.
The following instructions assume that you are working in that directory.

#### text articles
Text articles can be created by adding standard markdown files using your favourite text editor.

#### executable notebook
If you want to add a new notebook, you can either start out from an existing **MyST** Markdown file by copying and modifying it, or you can create a new one from the jupyter notebook menu using `File` > `New Text Notebook` > `MyST Markdown`.
If you already have an existing ipython notebook and want to convert it to **MyST**, you can do this by running
```bash
jupytext --to myst your_notebook.ipynb
```
This will create a new markdown file named `your_notebook.md`.
After conversion, the `ipynb` file is not needed anymore and it should not be committed into the repository.

#### entry in the table of contents
After preparing your article or notebook, you'll have to add it into the table of contents, such that it will actually show up in the compiled book.
You can do this by modifying `_toc.yml`, where you can add the articles file name without suffix.

### compile to PDF

If you've got a LaTeX environment available (e.g. TeXLive), you can also compile the book into a single PDF file.
To do so, just run:

```bash
jb build how_to_eurec4a --builder pdflatex
```
