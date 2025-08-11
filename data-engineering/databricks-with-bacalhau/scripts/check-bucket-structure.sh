#!/bin/bash

echo "Checking S3 bucket structure..."
echo "================================"

for bucket in \
  "expanso-databricks-ingestion-us-west-2" \
  "expanso-databricks-validated-us-west-2" \
  "expanso-databricks-enriched-us-west-2" \
  "expanso-databricks-aggregated-us-west-2"
do
  echo ""
  echo "Bucket: $bucket"
  echo "-------------------"
  
  # Count nested files
  nested=$(aws s3 ls s3://$bucket/ --recursive --no-paginate 2>/dev/null | \
    grep -E "/(data|raw|validated|enriched|aggregated|ingestion)/" | wc -l)
  
  # Count flat files  
  flat=$(aws s3 ls s3://$bucket/ --no-paginate 2>/dev/null | \
    grep -E "^[0-9]{8}_[0-9]{6}_[a-z0-9]+\.json" | wc -l)
  
  echo "  Nested files (old structure): $nested"
  echo "  Flat files (new structure): $flat"
  
  if [ $nested -gt 0 ]; then
    echo "  ⚠️  Has old nested structure - needs cleanup"
  fi
done

echo ""
echo "To fix LOCATION_OVERLAP errors:"
echo "1. Archive old nested files to _archive/ prefix"
echo "2. Or delete them if no longer needed"
echo "3. Keep only flat files at bucket root"
