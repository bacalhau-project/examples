# Cleanup Rules - NEVER DELETE These Files

## Critical Files That Must NEVER Be Deleted

### 1. Entry Point Scripts (Even if unreferenced)
- `build.sh` - Builds Docker images
- `run.sh` - Runs the application
- `deploy.sh` - Deploys to various targets
- `test-pipeline.sh` - Runs tests
- `docker-run-helper.sh` - Docker utilities
- Any `start-*.sh` scripts - Runtime tools

### 2. Configuration Files
- `.env.example` - Template for environment setup
- `Dockerfile` - Container definitions
- `docker-compose.yml` - Container orchestration
- `pyproject.toml` - Python project config
- `.gitignore` - Git configuration
- `*.yaml` in jobs/ - Bacalhau job definitions

### 3. Documentation
- `README.md` - Main documentation
- `DEVELOPMENT_RULES.md` - Development guidelines
- `CLEANUP_RULES.md` - This file
- Any `*.md` files in docs/

### 4. Test Infrastructure
- `test-*.sh` - Test scripts
- `validate*.py` - Validation scripts
- Any files in `tests/` directory

### 5. Scripts Directory
- Everything in `scripts/` - These are operational tools
- Even if not referenced by code, they're used by operators

## Cleanup Guidelines

### BEFORE Deleting Anything:

1. **Check if it's an entry point**
   - Shell scripts (*.sh) are usually entry points
   - Main.py files are entry points
   - Scripts in scripts/ are operational tools

2. **Check if it's infrastructure**
   - Build files (build.*, Makefile, etc.)
   - Deploy files (deploy.*, setup.*)
   - Docker-related files
   - CI/CD files (.github/, .gitlab-ci.yml, etc.)

3. **Check if it's documentation**
   - README files at any level
   - Docs directories
   - Example files (*.example)

4. **Check if it's configuration**
   - .env files and templates
   - Config files (*.conf, *.yaml, *.toml)
   - IDE settings (.vscode/, .idea/)

### Safe to Clean:

1. **Generated files**
   - `__pycache__/` directories
   - `*.pyc` files
   - `.pytest_cache/`
   - `node_modules/` (if package.json exists)
   - `venv/`, `.venv/` (virtual environments)

2. **Temporary files**
   - `*.tmp`, `*.temp`
   - `*.log` (unless in designated log directory)
   - `.DS_Store` (macOS)
   - `Thumbs.db` (Windows)

3. **Build artifacts**
   - `dist/`, `build/` (if they're build outputs)
   - `*.egg-info/`
   - Coverage reports (htmlcov/, .coverage)

4. **Old/Archive directories**
   - Directories clearly marked as archive/old/backup
   - But ASK before deleting if unsure

## The Golden Rule

**When in doubt, DON'T DELETE**

If you're not 100% certain a file is safe to delete:
1. Ask the user first
2. Move to an archive directory instead of deleting
3. Create a backup before cleanup

## Cleanup Command Template

```bash
# Safe cleanup script template
#!/bin/bash

# SAFE: Clean Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# SAFE: Clean test cache  
rm -rf .pytest_cache

# SAFE: Clean coverage
rm -rf htmlcov .coverage

# SAFE: Clean OS files
find . -type f -name ".DS_Store" -delete
find . -type f -name "Thumbs.db" -delete

# SAFE: Clean temp files
find . -type f -name "*.tmp" -delete
find . -type f -name "*.temp" -delete

# NEVER DO THIS:
# rm -rf *.sh  # NO! These are entry points
# rm -rf scripts/  # NO! These are tools
# rm -rf docs/  # NO! This is documentation
```

## File Preservation Priority

1. **Priority 1 - NEVER DELETE**
   - Entry points (main.py, *.sh)
   - Configuration (.env*, Dockerfile, etc.)
   - Documentation (*.md, docs/)

2. **Priority 2 - ASK FIRST**
   - Scripts directory contents
   - Test files
   - Example files
   - Anything you're unsure about

3. **Priority 3 - SAFE TO CLEAN**
   - Cache files
   - Compiled bytecode
   - OS-generated files
   - Clearly temporary files