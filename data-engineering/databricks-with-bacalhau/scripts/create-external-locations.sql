-- Create External Locations using existing storage credential
-- Storage Credential: expanso-databricks-s3-credential-us-west-2

-- Verify the storage credential exists
SHOW STORAGE CREDENTIALS;

-- Create external locations for data buckets
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_ingestion_data
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-ingestion-us-west-2/ingestion/'
);

CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_validated_data
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-validated-us-west-2/validated/'
);

CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_enriched_data
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-enriched-us-west-2/enriched/'
);

CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_aggregated_data
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-aggregated-us-west-2/aggregated/'
);

-- Create external locations for system buckets
CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_checkpoints
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-checkpoints-us-west-2/'
);

CREATE EXTERNAL LOCATION IF NOT EXISTS expanso_metadata
WITH (
  STORAGE_CREDENTIAL = `expanso-databricks-s3-credential-us-west-2`,
  URL = 's3://expanso-databricks-metadata-us-west-2/'
);

-- Grant permissions on all external locations to account users
GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_ingestion_data TO `account users`;

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_validated_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_validated_data TO `account users`;

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_enriched_data TO `account users`;

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_aggregated_data TO `account users`;

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_checkpoints TO `account users`;

GRANT CREATE MANAGED STORAGE ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT CREATE EXTERNAL TABLE ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT READ FILES ON EXTERNAL LOCATION expanso_metadata TO `account users`;
GRANT WRITE FILES ON EXTERNAL LOCATION expanso_metadata TO `account users`;

-- Verify all external locations were created
SHOW EXTERNAL LOCATIONS;

-- Test access to each location (optional)
-- LIST 'expanso_ingestion_data/';
-- LIST 'expanso_validated_data/';
-- LIST 'expanso_enriched_data/';
-- LIST 'expanso_aggregated_data/';
-- LIST 'expanso_checkpoints/';
-- LIST 'expanso_metadata/';