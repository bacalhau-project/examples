.PHONY: markdown clean requirements

all: requirements clean markdown

SRC_DIR := .
DST_DIR := rendered
SRC_FILES := $(shell find . -type f -name '*.ipynb' -not -path "./todo/*")
DST_FILES := $(patsubst $(SRC_DIR)/%.ipynb,$(DST_DIR)/%.md,$(SRC_FILES))


$(DST_DIR)/%.md: $(SRC_DIR)/%.ipynb
	mkdir -p $(dir $@)
	jupytext --to markdown -o $@ $<
	@echo

requirements:
ifeq (, $(shell which jupytext))
	$(error "No jupytext in $(PATH), please run pip install jupytext")
endif

markdown: requirements $(DST_FILES)

clean:
	rm -rf rendered