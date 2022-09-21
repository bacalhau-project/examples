.PHONY: markdown clean markdown-requirements test-requirements  

all: markdown-requirements test-requirements clean markdown test

SRC_DIR := .
DST_DIR := rendered
# Markdown files to render
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))

# Image files to copy
SRC_IMGS := $(shell find . -type f -regex '\(.*jpg\|.*png\|.*jpeg\|.*JPG\|.*PNG\|.*mp4\)' -not -path "./todo/*" -not -path "./rendered/*")
DST_IMGS := $(patsubst %,$(DST_DIR)/%,$(SRC_IMGS))

# Need to process these one at a time so that we can extract the right output dir
# Otherwise the embedded images will be saved with non-relative paths, which are required for docusaurus
$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(@D)
	jupyter nbconvert --to markdown --output-dir=$(@D) --output=$(@F) \
		--TagRemovePreprocessor.enabled=True \
		--TagRemovePreprocessor.remove_cell_tags=remove_cell \
		--TagRemovePreprocessor.remove_all_outputs_tags=remove_output \
		--TagRemovePreprocessor.remove_input_tags=remove_input \
		$<
	@echo

# Copy images to the rendered directory
$(DST_DIR)/%: $(SRC_IMGS)
	mkdir -p $(@D)
	cp $< $@

markdown-requirements:
ifeq (, $(shell which jupyter))
	$(error "No jupyter in $(PATH), please run pip install nbconvert")
endif

test-requirements:
ifeq (, $(shell which pytest))
	$(error "No pytest in $(PATH), please run pip install nbmake")
endif

markdown: markdown-requirements $(DST_FILES) $(DST_IMGS)

test: test-requirements
	pytest --nbmake --ignore=./todo/ --durations=0

clean:
	rm -rf rendered