#!/usr/bin/env bash
# /// script
# dependencies = []
# ///

set -euo pipefail

echo "Repository Cleanup Script"
echo "========================"
echo

# Function to confirm action
confirm() {
    read -p "$1 [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]]
}

# Clean generated files
if confirm "Remove generated files (latest-tag, .latest-*, etc)?"; then
    rm -f latest-tag .latest-* pipeline_config.db \
          set-environment.sh additional-commands.sh
    echo "✓ Removed generated files"
fi

# Clean test files
if confirm "Remove temporary test files?"; then
    rm -f test-*.yaml test-*.py test-*.sh \
          debug-*.py diagnose-*.py fix-*.py \
          simple-cleanup.py show-upload-status.py quick-*.sh
    echo "✓ Removed test files"
fi

# Clean old directories
if confirm "Remove old directories (output/, sample-sensor/)?"; then
    rm -rf output/ sample-sensor/
    echo "✓ Removed old directories"
fi

# Clean Python cache
if confirm "Remove Python cache files?"; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    echo "✓ Removed Python cache"
fi

# Clean Docker artifacts
if confirm "Remove Docker build artifacts?"; then
    docker system prune -f 2>/dev/null || true
    echo "✓ Cleaned Docker artifacts"
fi

# Clean state files (optional)
if confirm "Remove state files (WARNING: This will reset upload tracking)?"; then
    rm -rf state/*.json state/*.db
    echo "✓ Removed state files"
fi

echo
echo "Cleanup complete! Current directory structure:"
echo "=============================================="
ls -la | head -20
echo
echo "Total files in root: $(ls -1 | wc -l)"