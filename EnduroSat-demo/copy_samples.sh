#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <target-input-dir> <num-images>"
  exit 1
fi

TARGET_DIR="$1"
NUM="$2"
SAMPLES_DIR="samples"

mkdir -p "$TARGET_DIR"

find "$SAMPLES_DIR" -maxdepth 1 -type f \( -iname "*.bmp" -o -iname "*.jpg" -o -iname "*.jpeg" \) \
  | shuf \
  | head -n "$NUM" \
  | while read -r file; do
      cp "$file" "$TARGET_DIR"
    done
