#!/bin/bash
# Cleanup and organize the databricks-with-bacalhau repository

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Repository Cleanup and Organization${NC}"
echo -e "${GREEN}========================================${NC}"

# Get repo root (parent of spot directory)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

echo -e "\n${YELLOW}Current directory: $REPO_ROOT${NC}"

# Create organized directory structure
echo -e "\n${GREEN}Creating organized directory structure...${NC}"
mkdir -p archive/{scripts,configs,docs,tests}
mkdir -p tools/{setup,testing,deployment}
mkdir -p config

# Move documentation files to docs or archive/docs
echo -e "\n${YELLOW}Organizing documentation...${NC}"
for file in *.md; do
    if [[ -f "$file" ]]; then
        case "$file" in
            README.md|AGENTS.md|CLAUDE.md)
                echo "  Keeping $file in root (essential docs)"
                ;;
            *)
                echo "  Moving $file → archive/docs/"
                mv "$file" archive/docs/ 2>/dev/null || true
                ;;
        esac
    fi
done

# Move test scripts to tools/testing
echo -e "\n${YELLOW}Organizing test scripts...${NC}"
for file in test-*.{sh,py} quick-test.sh run-tests.sh; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → tools/testing/"
        mv "$file" tools/testing/ 2>/dev/null || true
    fi
done

# Move setup scripts to tools/setup
echo -e "\n${YELLOW}Organizing setup scripts...${NC}"
for file in setup-*.{sh,py,sql} quick-setup.sh fix-*.py generate-*.py; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → tools/setup/"
        mv "$file" tools/setup/ 2>/dev/null || true
    fi
done

# Move deployment/run scripts to tools/deployment
echo -e "\n${YELLOW}Organizing deployment scripts...${NC}"
for file in start-*.{sh,py} run-*.{sh,py} show-*.py diagnose-*.py debug-*.py; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → tools/deployment/"
        mv "$file" tools/deployment/ 2>/dev/null || true
    fi
done

# Move cleanup scripts to archive/scripts
echo -e "\n${YELLOW}Organizing cleanup scripts...${NC}"
for file in cleanup-*.py simple-cleanup.py query-*.py; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → archive/scripts/"
        mv "$file" archive/scripts/ 2>/dev/null || true
    fi
done

# Move config files to config directory
echo -e "\n${YELLOW}Organizing configuration files...${NC}"
for file in *.yaml *.yml *.json; do
    if [[ -f "$file" ]]; then
        case "$file" in
            databricks-uploader-config.yaml|databricks-s3-uploader-config.yaml)
                echo "  Keeping $file in root (active config)"
                ;;
            *)
                echo "  Moving $file → config/"
                mv "$file" config/ 2>/dev/null || true
                ;;
        esac
    fi
done

# Move additional scripts to archive
echo -e "\n${YELLOW}Archiving additional scripts...${NC}"
for file in additional-commands.sh* generate-and-deploy.sh update-*.sh; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → archive/scripts/"
        mv "$file" archive/scripts/ 2>/dev/null || true
    fi
done

# Move databricks-specific setup to archive
echo -e "\n${YELLOW}Archiving databricks setup files...${NC}"
for file in databricks-setup.py *-autoloader.py; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → archive/scripts/"
        mv "$file" archive/scripts/ 2>/dev/null || true
    fi
done

# Clean up dot files that shouldn't be in root
echo -e "\n${YELLOW}Cleaning up temporary files...${NC}"
for file in .latest-* latest-tag; do
    if [[ -f "$file" ]]; then
        echo "  Removing $file"
        rm -f "$file"
    fi
done

# Move Docker helper scripts
echo -e "\n${YELLOW}Organizing Docker scripts...${NC}"
for file in docker-*.sh; do
    if [[ -f "$file" ]]; then
        echo "  Moving $file → tools/deployment/"
        mv "$file" tools/deployment/ 2>/dev/null || true
    fi
done

# Create a simple run script in root
echo -e "\n${GREEN}Creating simplified run scripts...${NC}"
cat > run-uploader.sh << 'EOF'
#!/bin/bash
# Simple script to run the databricks uploader
docker run \
    --name databricks-uploader \
    --rm \
    -e PYTHONUNBUFFERED=1 \
    -v "$(pwd)/databricks-uploader-config.yaml":/app/config.yaml:ro \
    -v "$(pwd)/credentials":/bacalhau_data/credentials:ro \
    -v "$(pwd)/sample-sensor/data/sensor_data.db":/app/sensor_data.db \
    -v "$(pwd)/state":/app/state \
    ghcr.io/bacalhau-project/databricks-uploader:latest
EOF
chmod +x run-uploader.sh

# Create index of moved files
echo -e "\n${GREEN}Creating file index...${NC}"
cat > MOVED_FILES.md << 'EOF'
# File Reorganization Index

This repository has been reorganized for clarity. Here's where to find things:

## Essential Files (kept in root)
- `README.md` - Main documentation
- `AGENTS.md` - Agent configuration
- `CLAUDE.md` - Claude AI guidance
- `build.sh` - Container build script
- `run.sh` - Main run script
- `run-uploader.sh` - Quick uploader start
- `databricks-uploader-config.yaml` - Active configuration

## Directory Structure
```
.
├── archive/           # Historical/deprecated files
│   ├── configs/      # Old configuration files
│   ├── docs/         # Additional documentation
│   ├── scripts/      # Deprecated scripts
│   └── tests/        # Old test files
├── config/           # Configuration files
├── credentials/      # AWS/Databricks credentials
├── databricks-uploader/  # Main uploader code
├── pipeline-manager/     # Pipeline management
├── scripts/          # Active utility scripts
├── spot/             # AWS Spot instance configs
├── state/            # Runtime state files
└── tools/            # Organized tooling
    ├── deployment/   # Deployment & run scripts
    ├── setup/        # Setup & configuration
    └── testing/      # Test scripts
```

## Quick Commands

### Build container
```bash
./build.sh databricks-uploader
```

### Run uploader
```bash
./run-uploader.sh
# or
docker logs -f databricks-uploader
```

### Run tests
```bash
tools/testing/run-tests.sh
```

### Setup environment
```bash
tools/setup/quick-setup.sh
```
EOF

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Cleanup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"

# Count files
REMAINING=$(ls -1 | wc -l)
echo -e "\nFiles in root reduced to: ${GREEN}$REMAINING${NC}"
echo -e "\nEssential files kept in root:"
ls -1 | grep -E '\.(sh|yaml|md)$' | head -20

echo -e "\n${YELLOW}See MOVED_FILES.md for the new organization${NC}"
echo -e "${YELLOW}Old files are in archive/ and can be deleted if not needed${NC}"