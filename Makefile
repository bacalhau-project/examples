PRECOMMIT_HOOKS_INSTALLED ?= $(shell grep -R "pre-commit.com" .git/hooks)
PYTHON_RUNNER := poetry run

.PHONY: all  
all: markdown-requirements test-requirements clean markdown convert test

markdown-requirements:
ifeq (, $(shell poetry run which jupyter))
	$(error "No jupyter in $(PATH), please run poetry add nbconvert")
endif

test-requirements:
	@echo "Checking build environment..."
ifeq (, $(shell poetry run which pytest))
	$(error "No pytest in $(PATH), please run poetry add nbmake")
endif
ifeq ($(PRECOMMIT_HOOKS_INSTALLED),)
	@echo "Pre-commit is not installed in .git/hooks/pre-commit. Please run 'make install-pre-commit' to install it."
	@exit 1
endif
	@echo "Build environment correct."

markdown: markdown-requirements $(DST_FILES) $(DST_IMGS)

convert:
	@echo "Converting notebooks to markdown..."
	$(PYTHON_RUNNER) python build.py
	@echo "Conversion complete."

test: test-requirements
	${PYTHON_RUNNER} pytest --nbmake --ignore=./todo/ --durations=0

clean:
	rm -rf rendered

# Run init repo after cloning it
.PHONY: init
init:
	@ops/repo_init.sh 1>/dev/null
	@echo "Build environment initialized."

# Run install pre-commit
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
