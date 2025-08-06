
-- Create storage credential
CREATE STORAGE CREDENTIAL IF NOT EXISTS expanso_s3_credential
WITH (
  AWS_IAM_ROLE = 'arn:aws:iam::767397752906:role/databricks-unity-catalog-expanso-role'
);

-- Grant usage on storage credential
GRANT USAGE ON STORAGE CREDENTIAL expanso_s3_credential TO `account users`;


-- Create external location for ingestion
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_ingestion_data
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-ingestion-us-west-2/ingestion/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;


-- Create external location for validated
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_validated_data
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-validated-us-west-2/validated/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_validated_data TO `account users`;


-- Create external location for enriched
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_enriched_data
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-enriched-us-west-2/enriched/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;


-- Create external location for aggregated
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_aggregated_data
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-aggregated-us-west-2/aggregated/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;


-- Create external location for checkpoints
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_checkpoints
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-checkpoints-us-west-2/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;


-- Create external location for metadata
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_metadata
WITH (
  STORAGE_CREDENTIAL = expanso_s3_credential,
  URL = 's3://expanso-databricks-metadata-us-west-2/'
);

-- Grant permissions on external location
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_metadata TO `account users`;


-- Verify the setup
SHOW STORAGE CREDENTIALS;
SHOW EXTERNAL LOCATIONS;
