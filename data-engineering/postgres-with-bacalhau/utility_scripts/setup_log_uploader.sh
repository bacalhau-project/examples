#!/bin/bash

# Exit on error
set -e

# Default config path
CONFIG_PATH="../config.yaml"
if [ -n "$1" ]; then
    CONFIG_PATH="$1"
fi

# Read PostgreSQL connection details
HOST=$(yq '.postgresql.host' "$CONFIG_PATH")
PORT=$(yq '.postgresql.port' "$CONFIG_PATH")
USER=$(yq '.postgresql.user' "$CONFIG_PATH")
PASSWORD=$(yq '.postgresql.password' "$CONFIG_PATH")
DATABASE=$(yq '.postgresql.database' "$CONFIG_PATH")

echo "Setting up PostgreSQL permissions for log uploader..."

# Create a temporary SQL file
cat > setup_permissions.sql << EOF
-- Ensure schema exists
CREATE SCHEMA IF NOT EXISTS log_analytics;

-- Grant usage on schema
GRANT USAGE ON SCHEMA log_analytics TO PUBLIC;

-- Grant permissions on all tables
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA log_analytics TO PUBLIC;

-- Grant permissions for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA log_analytics 
    GRANT SELECT, INSERT ON TABLES TO PUBLIC;
EOF

# Run the SQL file
PGPASSWORD="$PASSWORD" psql \
    -h "$HOST" \
    -p "$PORT" \
    -U "$USER" \
    -d "$DATABASE" \
    -f setup_permissions.sql

# Clean up
rm setup_permissions.sql

echo "Done. Database users now have minimal permissions to write to PostgreSQL tables." 