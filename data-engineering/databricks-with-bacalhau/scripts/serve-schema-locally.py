#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.100.0",
#     "uvicorn>=0.23.0",
# ]
# ///
"""
Local Schema Server

Serves the wind turbine JSON schema locally for testing.
This allows testing without AWS credentials or S3 access.
"""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(title="Wind Turbine Schema Server")

# Schema directory
SCHEMA_DIR = Path(__file__).parent.parent / "databricks-uploader"


@app.get("/")
async def root():
    """Root endpoint with available schemas."""
    return {
        "service": "Wind Turbine Schema Server",
        "schemas": ["/schemas/wind-turbine-schema-v1.0.json", "/schemas/latest"],
    }


@app.get("/schemas/{schema_name}")
async def get_schema(schema_name: str):
    """
    Get a specific schema by name.

    Args:
        schema_name: Schema file name or 'latest' for the current version
    """
    if schema_name == "latest":
        schema_name = "wind-turbine-schema-v1.0.json"

    # Security: only allow specific schema files
    allowed_schemas = ["wind-turbine-schema.json", "wind-turbine-schema-v1.0.json"]

    if not any(schema_name == allowed for allowed in allowed_schemas):
        raise HTTPException(status_code=404, detail="Schema not found")

    # Try multiple locations
    schema_paths = [
        SCHEMA_DIR / schema_name,
        SCHEMA_DIR / f"wind-turbine-schema.json",
        Path(__file__).parent / schema_name,
    ]

    for schema_path in schema_paths:
        if schema_path.exists():
            with open(schema_path, "r") as f:
                schema = json.load(f)
            return JSONResponse(content=schema)

    raise HTTPException(status_code=404, detail=f"Schema file not found: {schema_name}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    print("🚀 Starting Wind Turbine Schema Server")
    print("📍 Access at: http://localhost:8000")
    print("📄 Schema endpoint: http://localhost:8000/schemas/latest")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
