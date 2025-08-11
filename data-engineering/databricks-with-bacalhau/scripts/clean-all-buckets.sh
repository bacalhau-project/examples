#!/bin/bash

# Clean all S3 buckets for a fresh demo run
# This removes ALL files from ALL pipeline buckets

echo "=========================================="
echo "CLEANING ALL DEMO BUCKETS"
echo "=========================================="
echo ""
echo "⚠️  This will DELETE all files from:"
echo "  - expanso-databricks-ingestion-us-west-2"
echo "  - expanso-databricks-validated-us-west-2"
echo "  - expanso-databricks-enriched-us-west-2"
echo "  - expanso-databricks-aggregated-us-west-2"
echo "  - expanso-databricks-checkpoints-us-west-2"
echo ""
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted"
    exit 1
fi

echo ""
echo "Cleaning buckets..."

# Function to clean a bucket
clean_bucket() {
    local bucket=$1
    local name=$2
    
    echo ""
    echo "🧹 Cleaning $name bucket..."
    
    # Remove all objects (faster than rm --recursive for large buckets)
    aws s3 rm "s3://$bucket" --recursive --no-paginate 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "   ✅ $name bucket cleaned"
    else
        echo "   ⚠️  $name bucket was already empty or had an error"
    fi
}

# Clean each bucket
clean_bucket "expanso-databricks-ingestion-us-west-2" "INGESTION"
clean_bucket "expanso-databricks-validated-us-west-2" "VALIDATED"
clean_bucket "expanso-databricks-enriched-us-west-2" "ENRICHED"
clean_bucket "expanso-databricks-aggregated-us-west-2" "AGGREGATED"
clean_bucket "expanso-databricks-checkpoints-us-west-2" "CHECKPOINTS"

echo ""
echo "=========================================="
echo "✅ ALL BUCKETS CLEANED"
echo "=========================================="
echo ""
echo "Buckets are now empty and ready for a fresh demo run."
echo ""
echo "To start the demo:"
echo "1. Start the sensor: docker-compose up sensor"
echo "2. Start the uploader: docker-compose up uploader"
echo "3. Run the Databricks notebook"