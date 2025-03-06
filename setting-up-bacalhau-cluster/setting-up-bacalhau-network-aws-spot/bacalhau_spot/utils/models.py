"""
Data models for the spot instance management.
"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


class SpotInstanceStatus(Enum):
    """Status of a spot instance request."""
    INITIALIZING = "Initializing"
    REQUESTING = "Requesting"
    WAITING_FOR_FULFILLMENT = "Waiting for fulfillment"
    FULFILLED = "Fulfilled"
    TAGGING = "Tagging"
    RUNNING = "Running"
    FAILED = "Failed"
    TERMINATED = "Terminated"
    TIMEOUT = "Timeout"
    ERROR = "Error"


class ErrorType(Enum):
    """Types of errors that can occur."""
    CREDENTIAL_ISSUES = "credential_issues"
    CAPACITY_ISSUES = "capacity_issues"
    PRICE_ISSUES = "price_issues"
    CONFIG_ISSUES = "config_issues"
    NETWORK_ISSUES = "network_issues"
    UNKNOWN = "unknown"


@dataclass
class InstanceStatus:
    """Status of an instance."""
    region: str
    zone: str
    index: int = 0
    instance_id: Optional[str] = None
    
    id: str = field(init=False)
    status: SpotInstanceStatus = field(default=SpotInstanceStatus.INITIALIZING)
    detailed_status: str = ""
    start_time: float = field(default_factory=time.time)
    elapsed_time: float = 0
    
    public_ip: Optional[str] = None
    private_ip: Optional[str] = None
    vpc_id: Optional[str] = None
    spot_request_id: Optional[str] = None
    fulfilled: bool = False
    error_type: Optional[ErrorType] = None
    
    def __post_init__(self):
        """Generate a unique ID if not explicitly provided."""
        if hasattr(self, 'id') and self.id:
            return
            
        if self.instance_id:
            self.id = self.instance_id
        else:
            # Generate a deterministic ID based on region, zone, and index
            input_string = f"{self.region}-{self.zone}-{self.index}"
            hashed_string = hashlib.sha256(input_string.encode()).hexdigest()
            self.id = hashed_string[:6]  # Use first 6 chars for readability
    
    def update_elapsed_time(self) -> float:
        """Update and return the elapsed time."""
        self.elapsed_time = time.time() - self.start_time
        return self.elapsed_time
    
    def combined_status(self) -> str:
        """Get a combined status string for display."""
        if self.detailed_status and self.detailed_status != self.status.value:
            combined = self.detailed_status
            if len(combined) > 30:
                return combined[:27] + "..."
            return combined
        return self.status.value
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "region": self.region,
            "zone": self.zone,
            "status": self.status.value,
            "detailed_status": self.detailed_status,
            "elapsed_time": self.elapsed_time,
            "instance_id": self.instance_id,
            "spot_request_id": self.spot_request_id,
            "fulfilled": self.fulfilled,
            "public_ip": self.public_ip,
            "private_ip": self.private_ip,
            "vpc_id": self.vpc_id,
            "error_type": self.error_type.value if self.error_type else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'InstanceStatus':
        """Create an instance from a dictionary."""
        # Handle status enum conversion
        status_value = data.get("status", "Initializing")
        try:
            status = SpotInstanceStatus(status_value)
        except ValueError:
            status = SpotInstanceStatus.INITIALIZING
        
        # Handle error type enum conversion
        error_type_value = data.get("error_type")
        error_type = None
        if error_type_value:
            try:
                error_type = ErrorType(error_type_value)
            except ValueError:
                error_type = ErrorType.UNKNOWN
        
        # Create instance with basic fields
        instance = cls(
            region=data.get("region", ""),
            zone=data.get("zone", ""),
            index=0,  # Default index
            instance_id=data.get("instance_id"),
        )
        
        # Update additional fields
        instance.id = data.get("id", instance.id)
        instance.status = status
        instance.detailed_status = data.get("detailed_status", "")
        instance.elapsed_time = data.get("elapsed_time", 0)
        instance.public_ip = data.get("public_ip")
        instance.private_ip = data.get("private_ip")
        instance.vpc_id = data.get("vpc_id")
        instance.spot_request_id = data.get("spot_request_id")
        instance.fulfilled = data.get("fulfilled", False)
        instance.error_type = error_type
        
        # If start_time can be derived from elapsed_time, set it
        if instance.elapsed_time > 0:
            instance.start_time = time.time() - instance.elapsed_time
            
        return instance


@dataclass
class RegionStatistics:
    """Statistics for a single region."""
    region: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    zones: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def add_zone_stat(self, zone: str, total: int = 0, succeeded: int = 0, failed: int = 0):
        """Add statistics for a zone."""
        if zone not in self.zones:
            self.zones[zone] = {"total": 0, "succeeded": 0, "failed": 0}
        
        self.zones[zone]["total"] += total
        self.zones[zone]["succeeded"] += succeeded
        self.zones[zone]["failed"] += failed
        
        # Update region totals
        self.total += total
        self.succeeded += succeeded
        self.failed += failed
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "region": self.region,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "zones": self.zones,
        }


@dataclass
class OperationResult:
    """Result of an operation."""
    success: bool = False
    action: str = ""
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    end_time: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[ErrorType] = None
    result_summary: Dict = field(default_factory=dict)
    region_errors: Dict[str, Dict] = field(default_factory=dict)
    instances: List[InstanceStatus] = field(default_factory=list)
    destroyed_count: int = 0
    nuked_resources: Dict[str, int] = field(default_factory=dict)
    
    def complete(self, success: bool = True):
        """Mark the operation as complete."""
        self.success = success
        self.end_time = datetime.now(timezone.utc).isoformat()
        
    def set_error(self, error: str, error_type: ErrorType = ErrorType.UNKNOWN):
        """Set an error on the operation."""
        self.error = error
        self.error_type = error_type
        self.success = False
        
    def add_region_error(self, region: str, error: str, **kwargs):
        """Add a region-specific error."""
        self.region_errors[region] = {
            "error": error,
            **kwargs
        }
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "action": self.action,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "error": self.error,
            "error_type": self.error_type.value if self.error_type else None,
            "result_summary": self.result_summary,
            "region_errors": self.region_errors,
            "instances": [instance.to_dict() for instance in self.instances],
            "destroyed_count": self.destroyed_count,
            "nuked_resources": self.nuked_resources,
        }