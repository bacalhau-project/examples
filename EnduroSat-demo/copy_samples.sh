#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <node-data-dir> <num-images>"
  exit 1
fi

NODE_DIR="$1"
NUM="$2"
SAMPLES_DIR="samples"
INPUT_DIR="$NODE_DIR/input"
#OUTPUT_DIR="$NODE_DIR/output"

mk_and_fix() {
  local dir="$1"
  if [ ! -d "$dir" ]; then
    mkdir -p "$dir" 2>/dev/null || sudo mkdir -p "$dir"
  fi
  chmod a+rwx "$dir" 2>/dev/null || sudo chmod a+rwx "$dir"
}

mk_and_fix "$NODE_DIR"

mk_and_fix "$INPUT_DIR"
#mk_and_fix "$OUTPUT_DIR"

find "$SAMPLES_DIR" -maxdepth 1 -type f \( -iname "*.bmp" -o -iname "*.jpg" -o -iname "*.jpeg" \) \
  | shuf \
  | head -n "$NUM" \
  | while read -r file; do
      cp "$file" "$INPUT_DIR"
    done

echo "➤ Copied $NUM images into $INPUT_DIR"
