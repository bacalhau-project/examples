.PHONY: markdown clean requirements

all: requirements clean markdown

SRC_DIR := .
DST_DIR := rendered
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))


$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(dir $@)
	jupyter nbconvert --to markdown --output-dir=. --output=$@ $<
	@echo

requirements:
ifeq (, $(shell which jupyter))
	$(error "No jupyter in $(PATH), please run pip install nbconvert")
endif

markdown: requirements $(DST_FILES)

clean:
	rm -rf rendered