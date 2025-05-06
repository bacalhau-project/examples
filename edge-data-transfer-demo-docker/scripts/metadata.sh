#!/bin/bash

# Configuration
INPUT_DIR="/mnt/data"
OUTPUT_DIR="/bacalhau_data/metadata"
mkdir -p "$OUTPUT_DIR"

# Bacalhau Environment Variables
PARTITION_INDEX=${BACALHAU_PARTITION_INDEX:-0}
PARTITION_COUNT=${BACALHAU_PARTITION_COUNT:-5}
NODE_ID=${BACALHAU_NODE_ID:-$(hostname)}
JOB_ID=${BACALHAU_JOB_ID:-"unknown"}
EXECUTION_ID=${BACALHAU_EXECUTION_ID:-"unknown"}
JOB_NAME=${BACALHAU_JOB_NAME:-"unknown"}
JOB_NAMESPACE=${BACALHAU_JOB_NAMESPACE:-"default"}
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
PROCESSING_SLEEP=${PROCESSING_SLEEP:-2}

# Unique files for each node
NODE_CSV_FILE="$OUTPUT_DIR/metadata_${NODE_ID}.csv"
NODE_LOG_FILE="$OUTPUT_DIR/debug_${NODE_ID}.log"

# Function to compute file hash safely
compute_hash() {
    if [[ -f "$1" ]]; then
        sha256sum "$1" | awk '{print $1}'
    else
        echo "MISSING_FILE"
    fi
}

# Get the list of files, ensuring order is consistent across nodes
FILES=($(ls -1 "$INPUT_DIR"/*.bin 2>/dev/null | sort))
TOTAL_FILES=${#FILES[@]}

echo "Processing on Node: $NODE_ID | Partition Index: $PARTITION_INDEX | Total Files: $TOTAL_FILES" | tee -a "$NODE_LOG_FILE"

# Ensure CSV file has a header if it does not exist
if [ ! -f "$NODE_CSV_FILE" ]; then
    echo "file,node,partition_index,execution_id,job_id,timestamp" > "$NODE_CSV_FILE"
fi


for ((i=0; i<TOTAL_FILES; i++)); do
    if (( i % PARTITION_COUNT == PARTITION_INDEX )); then
        FILE=${FILES[$i]}
        FILE_NAME=$(basename "$FILE")

        if [[ ! -f "$FILE" ]]; then
            echo "❌ ERROR: File missing - $FILE_NAME" | tee -a "$NODE_LOG_FILE"
            continue
        fi

        echo "⏳ Sleeping for $PROCESSING_SLEEP second(s)..." | tee -a "$NODE_LOG_FILE"
        sleep "$PROCESSING_SLEEP"

        FILE_HASH=$(compute_hash "$FILE")
        METADATA_FILENAME="${FILE_NAME}.${NODE_ID}.metadata.json"
        METADATA_FILE="$OUTPUT_DIR/$METADATA_FILENAME"

        # Create metadata JSON
        cat <<EOF > "$METADATA_FILE"
{
    "file": "$FILE_NAME",
    "hash": "$FILE_HASH",
    "node": "$NODE_ID",
    "partition": "$PARTITION_INDEX",
    "execution_id": "$EXECUTION_ID",
    "job_id": "$JOB_ID",
    "job_name": "$JOB_NAME",
    "job_namespace": "$JOB_NAMESPACE",
    "timestamp": "$TIMESTAMP"
}
EOF

        echo "$FILE_NAME,$NODE_ID,$PARTITION_INDEX,$EXECUTION_ID,$JOB_ID,$TIMESTAMP" >> "$NODE_CSV_FILE"

        echo "✅ Processed: $FILE_NAME -> $METADATA_FILENAME" | tee -a "$NODE_LOG_FILE"
    fi
done

echo "✅ Metadata generation complete for Node $NODE_ID (Partition $PARTITION_INDEX)" | tee -a "$NODE_LOG_FILE"
echo "CSV metadata saved to $NODE_CSV_FILE" | tee -a "$NODE_LOG_FILE"
