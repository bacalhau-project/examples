PRECOMMIT_HOOKS_INSTALLED ?= $(shell grep -R "pre-commit.com" .git/hooks)
PYTHON_RUNNER := poetry run

.PHONY: all  
all: init convert test

ifeq ($(PRECOMMIT_HOOKS_INSTALLED),)
	@echo "Pre-commit is not installed in .git/hooks/pre-commit. Please run 'make install-pre-commit' to install it."
	@exit 1
endif
	@echo "Build environment correct."

SRC_DIR := .
DST_DIR := rendered
# Markdown files to render
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*" -not -path "./templates/*" -not -path "./$(DST_DIR)/*" -not -path "./docs.bacalhau.org/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))

# Image files to copy
SRC_IMGS := $(shell find . -type f -regex '\(.*jpg\|.*png\|.*jpeg\|.*JPG\|.*PNG\|.*mp4\)' -not -path "./todo/*" -not -path "./$(DST_DIR)/*" -not -path "./templates/*" -not -path "./docs.bacalhau.org/*")
DST_IMGS := $(patsubst %,$(DST_DIR)/%,$(SRC_IMGS))

# Need to process these one at a time so that we can extract the right output dir
# Otherwise the embedded images will be saved with non-relative paths, which are required for docusaurus
$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(@D)
	${PYTHON_RUNNER} jupyter nbconvert --to markdown --output-dir=$(@D) --output=$(@F) \
		--TagRemovePreprocessor.enabled=True \
		--TagRemovePreprocessor.remove_cell_tags=remove_cell \
		--TagRemovePreprocessor.remove_all_outputs_tags=remove_output \
		--TagRemovePreprocessor.remove_input_tags=remove_input \
		$<
# Remove %%bash from the file (this command works both on bsd/macs and linux)
# grep -v "%%bash" $@ > temp && mv temp $@
# @echo

# Copy images to the rendered directory
$(DST_DIR)/%: $(SRC_DIR)/%
	mkdir -p $(@D)
	cp $< $@

convert: init $(DST_FILES) $(DST_IMGS)

# Exclude the Terraform folder from conversion
SRC_FILES_NO_TF := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*" -not -path "./templates/*" -not -path "./$(DST_DIR)/*" -not -path "./docs.bacalhau.org/*" -not -path "./case-studies/duckdb-log-processing/terraform/*")
DST_FILES_NO_TF := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES_NO_TF))

convert: init $(DST_FILES_NO_TF) $(DST_IMGS)


# Usage: Run tests on notebooks with `make test`
#		 Run tests on a specific notebook with `make test notebook.ipynb`
.PHONY: test
test: init
	${PYTHON_RUNNER} pytest --nbmake --ignore=./todo/ --durations=0 $(filter-out $@, $(MAKECMDGOALS))

.PHONY: clean
clean:
	rm -rf rendered
	rm -rf docs.bacalhau.org

.PHONY: init
init:
	@ops/repo_init.sh
	@echo "Build environment initialized."

.PHONY: install-pre-commit
install-pre-commit:
	@ops/install_pre_commit.sh 1>/dev/null
	@echo "Pre-commit installed."

################################################################################
# Target: precommit
################################################################################
.PHONY: precommit
precommit: test-requirements
	${PRECOMMIT} run --all 
	git ls-files -o | xargs rm; find . -type d -empty -delete

.PHONY: docs
docs: convert
	@echo "Building docs"
	if [ ! -d "docs.bacalhau.org" ]; then git clone https://github.com/bacalhau-project/docs.bacalhau.org/; fi
	cp -r rendered/* docs.bacalhau.org/docs/examples
	cd docs.bacalhau.org && yarn install && yarn build
