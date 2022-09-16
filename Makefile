.PHONY: markdown clean markdown-requirements test-requirements  

all: markdown-requirements test-requirements clean markdown test

SRC_DIR := .
DST_DIR := rendered
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))
SRC_IMGS := $(shell find . -type f -regex '\(.*jpg\|.*png\|.*jpeg\|.*JPG\|.*PNG\)' -not -path "./todo/*" -not -path "./rendered/*")
DST_IMGS := $(patsubst %,$(DST_DIR)/%,$(SRC_IMGS))

$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(@D)
	jupyter nbconvert --to markdown --output-dir=$(@D) --output=$(@F) $<
	@echo

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