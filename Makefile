.PHONY: markdown clean markdown-requirements test-requirements  

all: markdown-requirements test-requirements clean markdown test

SRC_DIR := .
DST_DIR := rendered
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))

$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(dir $@)
	jupyter nbconvert --to markdown --output-dir=. --output=$@ $<
	@echo

markdown-requirements:
ifeq (, $(shell which jupyter))
	$(error "No jupyter in $(PATH), please run pip install nbconvert")
endif

test-requirements:
ifeq (, $(shell which pytest))
	$(error "No pytest in $(PATH), please run pip install nbmake")
endif

markdown: markdown-requirements $(DST_FILES)

test: test-requirements
	pytest --nbmake --ignore=./todo/ --durations=0

clean:
	rm -rf rendered