#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi",
#     "uvicorn",
#     "pydantic>=2.0",
#     "sqlalchemy",
#     "pandas",
#     "boto3",
#     "python-multipart",
#     "aiofiles",
#     "websockets",
#     "sse-starlette",
# ]
# ///

"""
FastAPI Backend Service for Wind Turbine Data Pipeline UI

This module provides a RESTful API backend for monitoring and managing
the wind turbine data pipeline, including real-time metrics, pipeline
control, and data visualization endpoints.

Features:
- Real-time pipeline status monitoring
- Pipeline configuration management
- Data quality metrics and alerts
- S3 upload monitoring
- WebSocket support for live updates
- Server-sent events for dashboards
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from enum import Enum

import pandas as pd
import boto3
from fastapi import FastAPI, HTTPException, Query, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, text
from sse_starlette.sse import EventSourceResponse
import aiofiles

# Import our modules
from pipeline_manager import PipelineManager, PipelineType
from data_validation_framework import DataValidationFramework, ValidationLevel


# API Models
class PipelineStatus(BaseModel):
    """Current pipeline status."""
    pipeline_type: PipelineType
    updated_at: datetime
    updated_by: Optional[str]
    is_active: bool
    recent_uploads: int
    error_rate: float
    average_quality_score: float


class PipelineUpdate(BaseModel):
    """Pipeline update request."""
    pipeline_type: PipelineType
    updated_by: str = "api_user"
    reason: Optional[str] = None


class UploadMetrics(BaseModel):
    """S3 upload metrics."""
    total_uploads: int
    total_size_mb: float
    buckets_used: Dict[str, int]
    upload_rate_per_minute: float
    error_count: int
    last_upload_time: Optional[datetime]


class DataQualityReport(BaseModel):
    """Data quality report."""
    timestamp: datetime
    total_records: int
    quality_score: float
    validation_passed: int
    validation_failed: int
    anomalies_detected: int
    recommendations: List[str]


class AlertConfig(BaseModel):
    """Alert configuration."""
    name: str
    metric: str
    threshold: float
    comparison: str = "greater_than"
    enabled: bool = True
    notification_channels: List[str] = ["email"]


class TurbineMetrics(BaseModel):
    """Real-time turbine metrics."""
    turbine_id: str
    timestamp: datetime
    power_output: float
    wind_speed: float
    rpm: float
    temperature: float
    vibration: float
    status: str
    efficiency: float


# Initialize FastAPI app
app = FastAPI(
    title="Wind Turbine Data Pipeline API",
    description="Backend API for monitoring and managing wind turbine data pipeline",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global connections
pipeline_manager = None
validation_framework = None
s3_client = None
websocket_clients = []


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global pipeline_manager, validation_framework, s3_client
    
    # Initialize pipeline manager
    db_path = "../sample-sensor/data/sensor_data.db"
    pipeline_manager = PipelineManager(db_path)
    
    # Initialize validation framework
    validation_framework = DataValidationFramework()
    
    # Initialize S3 client
    s3_client = boto3.client('s3')
    
    print("API Backend started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    # Close WebSocket connections
    for client in websocket_clients:
        await client.close()


# Pipeline Management Endpoints
@app.get("/api/pipeline/status", response_model=PipelineStatus)
async def get_pipeline_status():
    """Get current pipeline status."""
    try:
        current_config = pipeline_manager.get_current_pipeline()
        
        # Get recent metrics
        conn = sqlite3.connect(pipeline_manager.db_path)
        cursor = conn.cursor()
        
        # Get upload metrics from last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        cursor.execute("""
            SELECT COUNT(*), AVG(records_processed)
            FROM pipeline_executions
            WHERE started_at > ? AND pipeline_type = ?
        """, (one_hour_ago.isoformat(), current_config.pipeline_type.value))
        
        upload_count, avg_records = cursor.fetchone()
        upload_count = upload_count or 0
        
        # Get error rate
        cursor.execute("""
            SELECT COUNT(*) FROM pipeline_executions
            WHERE started_at > ? AND status = 'failed'
        """, (one_hour_ago.isoformat(),))
        
        error_count = cursor.fetchone()[0]
        error_rate = error_count / upload_count if upload_count > 0 else 0
        
        # Get average quality score (mock for now)
        quality_score = 0.85  # This would come from actual data validation
        
        conn.close()
        
        return PipelineStatus(
            pipeline_type=current_config.pipeline_type,
            updated_at=current_config.updated_at,
            updated_by=current_config.updated_by,
            is_active=current_config.is_active,
            recent_uploads=upload_count,
            error_rate=error_rate,
            average_quality_score=quality_score
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/pipeline/update", response_model=PipelineStatus)
async def update_pipeline(update: PipelineUpdate):
    """Update pipeline configuration."""
    try:
        # Update pipeline
        updated_config = pipeline_manager.set_pipeline(
            pipeline_type=update.pipeline_type,
            updated_by=update.updated_by,
            config_json={"reason": update.reason} if update.reason else None
        )
        
        # Broadcast update to WebSocket clients
        await broadcast_update({
            "type": "pipeline_update",
            "data": {
                "pipeline_type": updated_config.pipeline_type.value,
                "updated_by": update.updated_by,
                "timestamp": datetime.now().isoformat()
            }
        })
        
        # Return updated status
        return await get_pipeline_status()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/pipeline/history")
async def get_pipeline_history(limit: int = Query(default=100, le=1000)):
    """Get pipeline execution history."""
    try:
        history = pipeline_manager.get_execution_history(limit=limit)
        
        return {
            "history": [
                {
                    "id": exec.id,
                    "pipeline_type": exec.pipeline_type,
                    "started_at": exec.started_at,
                    "completed_at": exec.completed_at,
                    "records_processed": exec.records_processed,
                    "status": exec.status,
                    "error_message": exec.error_message
                }
                for exec in history
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# S3 Upload Monitoring
@app.get("/api/uploads/metrics", response_model=UploadMetrics)
async def get_upload_metrics(hours: int = Query(default=24, le=168)):
    """Get S3 upload metrics."""
    try:
        # Query upload state from database
        db_path = Path(pipeline_manager.db_path).parent / "uploader_config.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get metrics for time period
        time_ago = datetime.now() - timedelta(hours=hours)
        cursor.execute("""
            SELECT 
                COUNT(*) as total_uploads,
                SUM(records_uploaded) as total_records,
                scenario,
                MAX(last_upload_at) as last_upload
            FROM upload_state
            WHERE last_upload_at > ?
            GROUP BY scenario
        """, (time_ago.isoformat(),))
        
        results = cursor.fetchall()
        conn.close()
        
        # Aggregate metrics
        total_uploads = sum(r[0] for r in results)
        total_records = sum(r[1] for r in results if r[1])
        buckets_used = {r[2]: r[0] for r in results}
        last_upload = max((r[3] for r in results if r[3]), default=None)
        
        # Calculate upload rate
        minutes_elapsed = hours * 60
        upload_rate = total_uploads / minutes_elapsed if minutes_elapsed > 0 else 0
        
        # Estimate size (assume ~1KB per record)
        total_size_mb = (total_records * 1024) / (1024 * 1024) if total_records else 0
        
        return UploadMetrics(
            total_uploads=total_uploads,
            total_size_mb=total_size_mb,
            buckets_used=buckets_used,
            upload_rate_per_minute=upload_rate,
            error_count=0,  # Would need error tracking
            last_upload_time=datetime.fromisoformat(last_upload) if last_upload else None
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/uploads/recent")
async def get_recent_uploads(limit: int = Query(default=50, le=200)):
    """Get recent upload details."""
    try:
        # Query recent uploads
        db_path = Path(pipeline_manager.db_path).parent / "uploader_config.db"
        conn = sqlite3.connect(str(db_path))
        
        df = pd.read_sql_query("""
            SELECT 
                table_name,
                scenario,
                last_timestamp,
                last_upload_at,
                records_uploaded,
                last_batch_id
            FROM upload_state
            ORDER BY last_upload_at DESC
            LIMIT ?
        """, conn, params=(limit,))
        
        conn.close()
        
        return {
            "uploads": df.to_dict(orient="records")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Data Quality Endpoints
@app.post("/api/quality/validate", response_model=DataQualityReport)
async def validate_data(file: UploadFile = File(...)):
    """Validate uploaded data file."""
    try:
        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        async with aiofiles.open(temp_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Load data
        if file.filename.endswith('.csv'):
            df = pd.read_csv(temp_path)
        elif file.filename.endswith('.parquet'):
            df = pd.read_parquet(temp_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # Run validation
        validation_results, _ = validation_framework.validate_data(df)
        anomaly_results = validation_framework.detect_anomalies(df)
        
        # Generate report
        report = validation_framework.generate_validation_report(
            validation_results, anomaly_results, df
        )
        
        # Clean up temp file
        temp_path.unlink()
        
        return DataQualityReport(
            timestamp=datetime.now(),
            total_records=report['summary']['total_records'],
            quality_score=report['summary']['overall_quality_score'],
            validation_passed=report['summary']['validations_passed'],
            validation_failed=report['summary']['validations_failed'],
            anomalies_detected=report['summary']['anomalies_detected'],
            recommendations=report['recommendations']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quality/metrics")
async def get_quality_metrics(hours: int = Query(default=24, le=168)):
    """Get data quality metrics over time."""
    try:
        # This would query a metrics database
        # For now, return mock data
        time_points = []
        now = datetime.now()
        
        for i in range(hours):
            timestamp = now - timedelta(hours=i)
            time_points.append({
                "timestamp": timestamp,
                "quality_score": 0.85 + 0.1 * (i % 3) / 3,  # Mock variation
                "records_processed": 1000 + i * 50,
                "anomalies_detected": 5 + i % 10
            })
        
        return {
            "metrics": time_points
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Real-time Data Endpoints
@app.get("/api/turbines/metrics")
async def get_turbine_metrics(
    farm_id: Optional[str] = None,
    limit: int = Query(default=100, le=1000)
):
    """Get real-time turbine metrics."""
    try:
        # Query latest sensor data
        db_path = "../sample-sensor/data/sensor_data.db"
        conn = sqlite3.connect(db_path)
        
        query = """
            SELECT 
                turbine_id,
                timestamp,
                MAX(CASE WHEN sensor_type = 'power' THEN value END) as power_output,
                MAX(CASE WHEN sensor_type = 'wind_speed' THEN value END) as wind_speed,
                MAX(CASE WHEN sensor_type = 'rpm' THEN value END) as rpm,
                MAX(CASE WHEN sensor_type = 'temperature' THEN value END) as temperature,
                MAX(CASE WHEN sensor_type = 'vibration' THEN value END) as vibration
            FROM sensor_readings
        """
        
        if farm_id:
            query += f" WHERE farm_id = '{farm_id}'"
        
        query += """
            GROUP BY turbine_id, timestamp
            ORDER BY timestamp DESC
            LIMIT ?
        """
        
        df = pd.read_sql_query(query, conn, params=(limit,))
        conn.close()
        
        # Calculate additional metrics
        df['status'] = df.apply(
            lambda row: 'operational' if row['power_output'] > 0 else 'idle',
            axis=1
        )
        df['efficiency'] = df.apply(
            lambda row: row['power_output'] / (row['wind_speed'] ** 3 * 0.5) 
            if row['wind_speed'] > 3 else 0,
            axis=1
        )
        
        return {
            "metrics": df.to_dict(orient="records")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Alert Management
@app.get("/api/alerts/config")
async def get_alert_configs():
    """Get alert configurations."""
    # This would be loaded from a configuration store
    return {
        "alerts": [
            AlertConfig(
                name="High Vibration",
                metric="vibration_max",
                threshold=50.0,
                comparison="greater_than",
                enabled=True,
                notification_channels=["email", "sms"]
            ),
            AlertConfig(
                name="Low Efficiency",
                metric="efficiency_mean",
                threshold=0.3,
                comparison="less_than",
                enabled=True,
                notification_channels=["email"]
            ),
            AlertConfig(
                name="Data Quality",
                metric="quality_score",
                threshold=0.7,
                comparison="less_than",
                enabled=True,
                notification_channels=["dashboard"]
            )
        ]
    }


@app.put("/api/alerts/config/{alert_name}")
async def update_alert_config(alert_name: str, config: AlertConfig):
    """Update alert configuration."""
    # This would update the configuration store
    return {
        "message": f"Alert '{alert_name}' updated successfully",
        "config": config
    }


# WebSocket for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        while True:
            # Send heartbeat
            await websocket.send_json({
                "type": "heartbeat",
                "timestamp": datetime.now().isoformat()
            })
            
            # Wait for messages or timeout
            await asyncio.sleep(30)
            
    except WebSocketDisconnect:
        websocket_clients.remove(websocket)


async def broadcast_update(message: Dict[str, Any]):
    """Broadcast update to all WebSocket clients."""
    disconnected = []
    
    for client in websocket_clients:
        try:
            await client.send_json(message)
        except:
            disconnected.append(client)
    
    # Remove disconnected clients
    for client in disconnected:
        websocket_clients.remove(client)


# Server-Sent Events for dashboards
@app.get("/api/events/stream")
async def event_stream():
    """Server-sent events stream for dashboard updates."""
    async def event_generator():
        while True:
            # Generate events
            yield {
                "event": "metrics_update",
                "data": json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "upload_rate": 12.5,  # Mock data
                    "quality_score": 0.89,
                    "active_turbines": 145
                })
            }
            
            await asyncio.sleep(5)  # Send update every 5 seconds
    
    return EventSourceResponse(event_generator())


# Export/Download Endpoints
@app.get("/api/export/report")
async def export_report(
    report_type: str = Query(..., regex="^(daily|weekly|monthly)$"),
    format: str = Query(default="pdf", regex="^(pdf|csv|excel)$")
):
    """Export reports in various formats."""
    try:
        # Generate report (mock implementation)
        if format == "csv":
            # Create CSV report
            df = pd.DataFrame({
                'date': pd.date_range(start='2024-01-01', periods=30),
                'energy_produced': np.random.randint(1000, 5000, 30),
                'efficiency': np.random.uniform(0.7, 0.9, 30),
                'uptime': np.random.uniform(0.9, 1.0, 30)
            })
            
            csv_path = f"/tmp/{report_type}_report.csv"
            df.to_csv(csv_path, index=False)
            
            return FileResponse(
                csv_path,
                media_type="text/csv",
                filename=f"{report_type}_report.csv"
            )
        
        else:
            raise HTTPException(status_code=501, detail="Format not implemented")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health Check
@app.get("/health")
async def health_check():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {
            "pipeline_manager": pipeline_manager is not None,
            "validation_framework": validation_framework is not None,
            "s3_client": s3_client is not None
        }
    }


# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )