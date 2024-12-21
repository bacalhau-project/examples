#!/bin/bash

# Logging functions
log() {
    local level="${1^^}"
    local message="$2"
    local color=""
    
    case "$level" in
        INFO)
            color="\033[0;34m"  # Blue
        ;;
        SUCCESS)
            color="\033[0;32m"  # Green
        ;;
        ERROR)
            color="\033[0;31m"  # Red
        ;;
        *)
            color="\033[0m"     # No color
        ;;
    esac
    
    echo -e "${color}[$level]${NC} $message"
}

# No color reset at end to allow further color manipulation if needed
NC='\033[0m'
