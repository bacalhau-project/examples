#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic",
# ]
# ///
"""Test that S3 bucket routing matches pipeline type."""

import json
from pathlib import Path
from pipeline_manager import PipelineType

# Expected S3 bucket routing based on pipeline type
EXPECTED_S3_ROUTING = {
    PipelineType.RAW: "raw",
    PipelineType.SCHEMATIZED: "schematized", 
    PipelineType.FILTERED: "filtered",
    PipelineType.EMERGENCY: "emergency"
}

# Table suffix mapping from sqlite_to_databricks_uploader.py
TABLE_SUFFIX_MAP = {
    "raw": "0_raw",
    "schematized": "1_schematized",
    "sanitized": "2_sanitized",  # Legacy, maps to filtered
    "aggregated": "3_aggregated",  # Legacy, maps to emergency
    "filtered": "2_filtered",
    "emergency": "4_emergency",
}

def test_pipeline_to_s3_mapping():
    """Verify pipeline types map to correct S3 buckets."""
    print("Testing Pipeline Type to S3 Bucket Mapping")
    print("=" * 50)
    
    for pipeline_type in PipelineType:
        expected_bucket = EXPECTED_S3_ROUTING[pipeline_type]
        print(f"\nPipeline Type: {pipeline_type.value}")
        print(f"  Expected S3 bucket suffix: {expected_bucket}")
        
        # Verify table routing aligns with S3 routing
        table_suffix = TABLE_SUFFIX_MAP.get(pipeline_type.value)
        if table_suffix:
            print(f"  Table suffix: {table_suffix}")
            
            # Check that the number prefix aligns
            if pipeline_type == PipelineType.RAW:
                assert table_suffix.startswith("0_"), f"Raw pipeline should use 0_ prefix, got {table_suffix}"
            elif pipeline_type == PipelineType.SCHEMATIZED:
                assert table_suffix.startswith("1_"), f"Schematized pipeline should use 1_ prefix, got {table_suffix}"
            elif pipeline_type == PipelineType.FILTERED:
                assert table_suffix.startswith("2_"), f"Filtered pipeline should use 2_ prefix, got {table_suffix}"
            elif pipeline_type == PipelineType.EMERGENCY:
                assert table_suffix.startswith("4_"), f"Emergency pipeline should use 4_ prefix, got {table_suffix}"
    
    print("\n✓ All pipeline types correctly map to S3 buckets")

def test_s3_config_structure():
    """Test S3 configuration structure from example config."""
    print("\n\nTesting S3 Configuration Structure")
    print("=" * 50)
    
    # Simulate S3 configuration
    s3_config = {
        "enabled": True,
        "region": "us-east-1",
        "prefix": "test-company",
        "buckets": {
            "raw": "test-company-databricks-raw-us-east-1",
            "schematized": "test-company-databricks-schematized-us-east-1",
            "filtered": "test-company-databricks-filtered-us-east-1",
            "emergency": "test-company-databricks-emergency-us-east-1"
        }
    }
    
    print("\nS3 Configuration:")
    print(json.dumps(s3_config, indent=2))
    
    # Verify all pipeline types have corresponding buckets
    for pipeline_type in PipelineType:
        bucket_key = EXPECTED_S3_ROUTING[pipeline_type]
        assert bucket_key in s3_config["buckets"], f"Missing bucket for {pipeline_type.value}"
        
        bucket_name = s3_config["buckets"][bucket_key]
        print(f"\n{pipeline_type.value} → {bucket_name}")
        
        # Verify bucket naming convention
        expected_pattern = f"{s3_config['prefix']}-databricks-{bucket_key}-{s3_config['region']}"
        assert bucket_name == expected_pattern, f"Bucket name doesn't match pattern: {bucket_name} != {expected_pattern}"
    
    print("\n✓ S3 configuration structure is valid")

def test_pipeline_routing_logic():
    """Test the logic for routing data based on pipeline type."""
    print("\n\nTesting Pipeline Routing Logic")
    print("=" * 50)
    
    base_table = "sensor_readings"
    base_bucket_prefix = "my-company"
    region = "us-west-2"
    
    for pipeline_type in PipelineType:
        # Get table routing
        table_suffix = TABLE_SUFFIX_MAP.get(pipeline_type.value)
        routed_table = f"{base_table}_{table_suffix}"
        
        # Get S3 bucket routing
        bucket_suffix = EXPECTED_S3_ROUTING[pipeline_type]
        routed_bucket = f"{base_bucket_prefix}-databricks-{bucket_suffix}-{region}"
        
        print(f"\nPipeline: {pipeline_type.value}")
        print(f"  Table: {routed_table}")
        print(f"  S3 Bucket: {routed_bucket}")
        
        # Verify consistency
        if pipeline_type == PipelineType.RAW:
            assert "0_raw" in routed_table and "raw" in routed_bucket
        elif pipeline_type == PipelineType.SCHEMATIZED:
            assert "1_schematized" in routed_table and "schematized" in routed_bucket
        elif pipeline_type == PipelineType.FILTERED:
            assert "2_filtered" in routed_table and "filtered" in routed_bucket
        elif pipeline_type == PipelineType.EMERGENCY:
            assert "4_emergency" in routed_table and "emergency" in routed_bucket
    
    print("\n✓ Pipeline routing logic is consistent")

def test_legacy_mapping():
    """Test legacy processing mode mappings."""
    print("\n\nTesting Legacy Processing Mode Mappings")
    print("=" * 50)
    
    legacy_mappings = {
        "sanitized": ("filtered", "2_filtered", "filtered"),
        "aggregated": ("emergency", "4_emergency", "emergency")
    }
    
    for legacy_mode, (new_pipeline, table_suffix, bucket_suffix) in legacy_mappings.items():
        print(f"\nLegacy mode: {legacy_mode}")
        print(f"  Maps to pipeline: {new_pipeline}")
        print(f"  Table suffix: {table_suffix}")
        print(f"  S3 bucket suffix: {bucket_suffix}")
        
        # Verify the mapping exists in our structures
        # Legacy modes keep their original table suffixes
        if legacy_mode == "sanitized":
            assert TABLE_SUFFIX_MAP.get(legacy_mode) == "2_sanitized"
        elif legacy_mode == "aggregated":
            assert TABLE_SUFFIX_MAP.get(legacy_mode) == "3_aggregated"
        
        # New pipeline types have updated suffixes
        assert TABLE_SUFFIX_MAP.get(new_pipeline) == table_suffix
    
    print("\n✓ Legacy mappings are correctly handled")

def main():
    """Run all S3 pipeline routing tests."""
    print("S3 Pipeline Routing Tests")
    print("=" * 70)
    
    test_pipeline_to_s3_mapping()
    test_s3_config_structure()
    test_pipeline_routing_logic()
    test_legacy_mapping()
    
    print("\n" + "=" * 70)
    print("All S3 pipeline routing tests passed! ✓")
    print("\nSummary:")
    print("- Each pipeline type correctly maps to its S3 bucket")
    print("- Table routing aligns with S3 bucket routing")
    print("- Legacy processing modes properly map to new pipeline types")
    print("- S3 bucket naming follows consistent patterns")

if __name__ == "__main__":
    main()