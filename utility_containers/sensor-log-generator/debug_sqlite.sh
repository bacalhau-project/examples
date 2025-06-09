#!/bin/bash

# SQLite Debug Script for Container Environments
# This script helps diagnose SQLite disk I/O errors

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default database path
DB_PATH="${1:-./data/sensor_data.db}"
DB_DIR=$(dirname "$DB_PATH")

echo -e "${BLUE}=== SQLite Database Diagnostics ===${NC}"
echo "Database: $DB_PATH"
echo "Time: $(date)"
echo

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo -e "${RED}ERROR: Database file not found at $DB_PATH${NC}"
    exit 1
fi

# Check file permissions
echo -e "${YELLOW}1. File Permissions:${NC}"
ls -la "$DB_PATH"* 2>/dev/null || echo "No database files found"
echo

# Check directory permissions
echo -e "${YELLOW}2. Directory Permissions:${NC}"
ls -ld "$DB_DIR"
echo "Directory writable: $([ -w "$DB_DIR" ] && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}")"
echo

# Check disk space
echo -e "${YELLOW}3. Disk Space:${NC}"
df -h "$DB_DIR"
echo

# Check inodes
echo -e "${YELLOW}4. Inode Usage:${NC}"
df -i "$DB_DIR"
echo

# Check for lock files
echo -e "${YELLOW}5. SQLite Lock Files:${NC}"
for ext in -journal -wal -shm; do
    lockfile="${DB_PATH}${ext}"
    if [ -f "$lockfile" ]; then
        echo -e "${YELLOW}Found:${NC} $lockfile (size: $(stat -f%z "$lockfile" 2>/dev/null || stat -c%s "$lockfile" 2>/dev/null || echo "unknown") bytes)"
        ls -la "$lockfile"
    fi
done
echo

# Check file locks (if lsof is available)
if command -v lsof &> /dev/null; then
    echo -e "${YELLOW}6. File Locks (lsof):${NC}"
    lsof "$DB_PATH" 2>/dev/null || echo "No locks detected or lsof not available"
    echo
fi

# Check SQLite integrity
echo -e "${YELLOW}7. Database Integrity Check:${NC}"
if command -v sqlite3 &> /dev/null; then
    echo "Running 'PRAGMA integrity_check'..."
    result=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1)
    if [ "$result" = "ok" ]; then
        echo -e "${GREEN}Database integrity: OK${NC}"
    else
        echo -e "${RED}Database integrity issues detected:${NC}"
        echo "$result"
    fi
    
    # Get database stats
    echo
    echo -e "${YELLOW}8. Database Statistics:${NC}"
    sqlite3 "$DB_PATH" << EOF
.mode column
.headers on
SELECT COUNT(*) as total_records FROM sensor_readings;
SELECT 
    printf('%.2f MB', page_count * page_size / 1024.0 / 1024.0) as database_size,
    page_count,
    page_size
FROM pragma_page_count(), pragma_page_size();
EOF
    
    # Check journal mode
    echo
    echo -e "${YELLOW}9. SQLite Settings:${NC}"
    sqlite3 "$DB_PATH" << EOF
.mode list
SELECT 'journal_mode: ' || journal_mode FROM pragma_journal_mode();
SELECT 'synchronous: ' || synchronous FROM pragma_synchronous();
SELECT 'temp_store: ' || temp_store FROM pragma_temp_store();
SELECT 'cache_size: ' || cache_size FROM pragma_cache_size();
EOF
else
    echo -e "${YELLOW}sqlite3 command not found - skipping integrity check${NC}"
fi

# Check for container environment
echo
echo -e "${YELLOW}10. Container Environment:${NC}"
if [ -f /.dockerenv ]; then
    echo -e "${BLUE}Running in Docker container${NC}"
elif [ -n "${KUBERNETES_SERVICE_HOST:-}" ]; then
    echo -e "${BLUE}Running in Kubernetes${NC}"
elif grep -q docker /proc/1/cgroup 2>/dev/null; then
    echo -e "${BLUE}Running in container (detected via cgroup)${NC}"
else
    echo "Not detected as container environment"
fi

# Check SQLITE_TMPDIR
echo
echo -e "${YELLOW}11. SQLite Temp Directory:${NC}"
if [ -n "${SQLITE_TMPDIR:-}" ]; then
    echo "SQLITE_TMPDIR=$SQLITE_TMPDIR"
    if [ -d "$SQLITE_TMPDIR" ]; then
        echo "Temp dir exists: YES"
        echo "Temp dir writable: $([ -w "$SQLITE_TMPDIR" ] && echo -e "${GREEN}YES${NC}" || echo -e "${RED}NO${NC}")"
        df -h "$SQLITE_TMPDIR" | tail -1
    else
        echo -e "${RED}Temp dir does not exist!${NC}"
    fi
else
    echo "SQLITE_TMPDIR not set (using system default)"
fi

# Recommendations
echo
echo -e "${BLUE}=== Recommendations ===${NC}"

# Check for common issues
issues_found=false

if [ ! -w "$DB_DIR" ]; then
    echo -e "${RED}• Database directory is not writable - fix with: chmod 777 $DB_DIR${NC}"
    issues_found=true
fi

if [ -f "${DB_PATH}-wal" ] && [ "$(stat -f%z "${DB_PATH}-wal" 2>/dev/null || stat -c%s "${DB_PATH}-wal" 2>/dev/null || echo 0)" -gt 1000000 ]; then
    echo -e "${YELLOW}• Large WAL file detected - consider running: sqlite3 $DB_PATH 'PRAGMA wal_checkpoint(TRUNCATE);'${NC}"
    issues_found=true
fi

if [ -z "${SQLITE_TMPDIR:-}" ] && [ -f /.dockerenv ]; then
    echo -e "${YELLOW}• Running in container without SQLITE_TMPDIR set - consider setting it${NC}"
    issues_found=true
fi

if [ "$issues_found" = false ]; then
    echo -e "${GREEN}No obvious issues detected${NC}"
fi

echo
echo -e "${BLUE}=== End of Diagnostics ===${NC}" 