PRECOMMIT_HOOKS_INSTALLED ?= $(shell grep -R "pre-commit.com" .git/hooks)
PYTHON_RUNNER := poetry run

.PHONY: all  
all: init convert test

ifeq ($(PRECOMMIT_HOOKS_INSTALLED),)
	@echo "Pre-commit is not installed in .git/hooks/pre-commit. Please run 'make install-pre-commit' to install it."
	@exit 1
endif
	@echo "Build environment correct."

.PHONY: convert
convert: init
	@echo "Converting notebooks to markdown..."
	$(PYTHON_RUNNER) python build.py
	@echo "Conversion complete."

# Usage: Run tests on notebooks with `make test`
#		 Run tests on a specific notebook with `make test notebook.ipynb`
.PHONY: test
test: init
	${PYTHON_RUNNER} pytest --nbmake --ignore=./todo/ --durations=0 $(filter-out $@, $(MAKECMDGOALS))

.PHONY: clean
clean:
	rm -rf rendered

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
