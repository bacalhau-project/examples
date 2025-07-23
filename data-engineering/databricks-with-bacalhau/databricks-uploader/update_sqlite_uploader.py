#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Script to show the key changes needed to integrate PipelineManager into sqlite_to_databricks_uploader.py
This is a reference implementation - the actual integration would modify the existing file.
"""

# Key changes to make in sqlite_to_databricks_uploader.py:

# 1. Add import at the top
from pipeline_manager import PipelineManager, PipelineType

# 2. Modify the ConfigWatcher class to remove processing_mode validation
# Remove lines 118-127 (processing_mode validation in update_config method)

# 3. In the main() function, initialize PipelineManager after SQLite setup (around line 720)
def integrate_pipeline_manager_example():
    """Example of integrating PipelineManager"""
    
    # After SQLite connection is established
    sqlite_path = "sensor_data.db"  # This comes from config
    
    # Initialize pipeline manager using the same SQLite database
    pipeline_manager = PipelineManager(sqlite_path, logger=logging.getLogger(__name__))
    
    # Check if we need to migrate from config
    if 'processing_mode' in cfg:
        # One-time migration from config file
        pipeline_manager.migrate_from_config(cfg)
        logging.info("Migrated pipeline configuration from config file to database")
    
    # Inside the main loop (around line 930):
    while True:
        try:
            # Get current pipeline configuration from database
            pipeline_config = pipeline_manager.get_current_pipeline()
            pipeline_type = pipeline_config.pipeline_type.value
            
            # Start execution tracking
            execution_id = pipeline_manager.start_execution()
            
            # Fetch new data
            df = pd.read_sql_query(query, conn_sqlite)
            
            if df.empty:
                logging.info("No new data to upload")
                pipeline_manager.complete_execution(execution_id, 0)
                continue
            
            # Process data based on pipeline type
            if pipeline_type == "raw":
                processed_df = process_raw_data(df, timestamp_field)
            elif pipeline_type == "schematized":
                processed_df = schematize_data(df)
            elif pipeline_type == "filtered":
                processed_df = sanitize_data(df, gps_fuzzing_config)  # Note: sanitized -> filtered mapping
            elif pipeline_type == "emergency":
                # Use aggregation config for emergency (they used aggregated -> emergency)
                processed_df = aggregate_data(df, aggregate_config)
            
            # Determine table suffix
            table_suffix_map = {
                "raw": "_raw",
                "schematized": "_schematized", 
                "filtered": "_filtered",
                "emergency": "_emergency"
            }
            
            table_suffix = table_suffix_map[pipeline_type]
            table_name_qualified = f"{databricks_database}.{databricks_table}{table_suffix}"
            
            # Upload data
            success = upload_batch_via_file(
                processed_df,
                table_name_qualified,
                cursor_db,
                pipeline_type,
            )
            
            if success:
                # Update state and complete execution
                pipeline_manager.complete_execution(execution_id, len(processed_df))
            else:
                pipeline_manager.complete_execution(
                    execution_id, 
                    0, 
                    error_message="Upload failed"
                )
                
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            if 'execution_id' in locals():
                pipeline_manager.complete_execution(
                    execution_id,
                    0,
                    error_message=str(e)
                )
            

# 4. Remove processing_mode from command line arguments (around line 350)
# Remove: parser.add_argument("--processing-mode", ...)

# 5. Remove processing_mode from validation (lines 492, 517-525)

# 6. Replace processing_mode retrieval (lines 866-876) with pipeline_manager call

# 7. Add new CLI command for pipeline management
def add_pipeline_cli_commands():
    """Example of adding pipeline management commands"""
    
    # Add subcommand to set pipeline
    parser.add_argument(
        "--set-pipeline",
        type=str,
        choices=["raw", "schematized", "filtered", "emergency"],
        help="Set the active pipeline type in the database"
    )
    
    # Handle the command
    if args.set_pipeline:
        pipeline_manager = PipelineManager(sqlite_path)
        pipeline_manager.set_pipeline(
            pipeline_type=PipelineType(args.set_pipeline),
            updated_by="cli"
        )
        print(f"Pipeline set to: {args.set_pipeline}")
        sys.exit(0)