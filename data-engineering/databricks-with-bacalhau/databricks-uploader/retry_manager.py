#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pyyaml>=6.0"
# ]
# ///

"""
Retry Manager for Pipeline

Centralized retry management that:
- Loads configuration from YAML
- Provides component-specific retry handlers
- Tracks global retry metrics
- Manages circuit breakers
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional, Type
from collections import defaultdict

from retry_handler import RetryHandler, RetryConfig
from pipeline_logging import get_logger


class RetryManager:
    """Centralized retry management."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
        
    def __init__(self, config_path: str = "retry_config.yaml"):
        """Initialize retry manager.
        
        Args:
            config_path: Path to retry configuration file
        """
        if hasattr(self, '_initialized'):
            return
            
        self.logger = get_logger("retry_manager")
        self.config_path = config_path
        self.config = self._load_config()
        self.handlers = {}
        self.global_metrics = defaultdict(int)
        
        self._initialized = True
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(self.config_path)
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                self.logger.info(f"Loaded retry configuration from {config_file}")
                return config
        else:
            self.logger.warning(f"Retry config not found at {config_file}, using defaults")
            return {
                "default": {
                    "max_attempts": 3,
                    "initial_wait": 1.0,
                    "max_wait": 60.0,
                    "exponential_base": 2.0,
                    "jitter": True,
                    "circuit_breaker_enabled": False,
                    "log_retries": True
                },
                "components": {}
            }
            
    def get_handler(self, component: str) -> RetryHandler:
        """Get or create retry handler for component.
        
        Args:
            component: Component name
            
        Returns:
            RetryHandler for the component
        """
        if component not in self.handlers:
            # Get component config or use default
            component_config = self.config.get("components", {}).get(
                component, 
                self.config.get("default", {})
            )
            
            # Create RetryConfig
            retry_config = RetryConfig(**self._build_config(component_config))
            
            # Create handler
            handler = RetryHandler(component, retry_config)
            self.handlers[component] = handler
            
            self.logger.info(f"Created retry handler for {component}")
            
        return self.handlers[component]
        
    def _build_config(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Build configuration with defaults.
        
        Args:
            config_dict: Component configuration
            
        Returns:
            Complete configuration dictionary
        """
        # Start with defaults
        default_config = self.config.get("default", {}).copy()
        
        # Override with component config
        default_config.update(config_dict)
        
        # Handle retriable errors
        if "retriable_errors" in default_config:
            # Convert string error names to exception classes
            error_classes = []
            for error_name in default_config["retriable_errors"]:
                try:
                    # Try to get builtin exception
                    if hasattr(__builtins__, error_name):
                        error_classes.append(getattr(__builtins__, error_name))
                    else:
                        # Default to generic exceptions
                        if "connection" in error_name.lower():
                            error_classes.append(ConnectionError)
                        elif "timeout" in error_name.lower():
                            error_classes.append(TimeoutError)
                        else:
                            error_classes.append(Exception)
                except:
                    error_classes.append(Exception)
                    
            default_config["retriable_errors"] = error_classes
            
        return default_config
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get global retry statistics.
        
        Returns:
            Dictionary with all component statistics
        """
        stats = {
            "components": {},
            "global_metrics": dict(self.global_metrics)
        }
        
        for component, handler in self.handlers.items():
            stats["components"][component] = handler.get_statistics()
            
        return stats
        
    def print_statistics(self):
        """Print formatted statistics."""
        stats = self.get_statistics()
        
        print("\n=== Global Retry Statistics ===\n")
        
        total_calls = 0
        total_retries = 0
        total_failures = 0
        
        for component, component_stats in stats["components"].items():
            if component_stats["total_calls"] > 0:
                print(f"{component}:")
                print(f"  Calls: {component_stats['total_calls']}")
                print(f"  Success rate: {component_stats['success_rate']:.2%}")
                print(f"  Retries: {component_stats['total_retries']}")
                print(f"  Circuit breaker: {component_stats['circuit_breaker_state']}")
                print()
                
                total_calls += component_stats["total_calls"]
                total_retries += component_stats["total_retries"]
                total_failures += component_stats["failed_calls"]
                
        if total_calls > 0:
            print("Overall:")
            print(f"  Total calls: {total_calls}")
            print(f"  Total retries: {total_retries}")
            print(f"  Total failures: {total_failures}")
            print(f"  Overall success rate: {(total_calls - total_failures) / total_calls:.2%}")
            
    def reset_statistics(self, component: Optional[str] = None):
        """Reset statistics.
        
        Args:
            component: Specific component to reset, or None for all
        """
        if component:
            if component in self.handlers:
                self.handlers[component].reset_statistics()
                self.logger.info(f"Reset statistics for {component}")
        else:
            for handler in self.handlers.values():
                handler.reset_statistics()
            self.global_metrics.clear()
            self.logger.info("Reset all retry statistics")


# Global retry manager instance
_retry_manager = None


def get_retry_manager() -> RetryManager:
    """Get the global retry manager instance.
    
    Returns:
        RetryManager instance
    """
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = RetryManager()
    return _retry_manager


def with_retry(component: str, **kwargs):
    """Decorator to add retry logic to a function.
    
    Args:
        component: Component name for retry configuration
        **kwargs: Override configuration
        
    Returns:
        Decorator function
    """
    manager = get_retry_manager()
    handler = manager.get_handler(component)
    return handler.with_retry(**kwargs)


def demo_retry_manager():
    """Demonstrate retry manager functionality."""
    print("\n=== Retry Manager Demo ===\n")
    
    # Get retry manager
    manager = get_retry_manager()
    
    # Example 1: Database operation with retry
    @with_retry("sqlite")
    def read_from_db():
        import random
        if random.random() < 0.5:
            raise ConnectionError("Database locked")
        return "Data from DB"
        
    # Example 2: S3 operation with retry
    @with_retry("s3")
    def upload_to_s3(bucket: str, key: str):
        import random
        if random.random() < 0.3:
            raise TimeoutError("S3 timeout")
        return f"Uploaded to {bucket}/{key}"
        
    # Example 3: Custom component
    custom_handler = manager.get_handler("my_custom_service")
    
    @custom_handler.with_retry(max_attempts=5)
    def call_custom_service():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Service unavailable")
        return "Custom service response"
        
    # Run operations
    print("Testing database operations...")
    for i in range(3):
        try:
            result = read_from_db()
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            
    print("\nTesting S3 operations...")
    for i in range(3):
        try:
            result = upload_to_s3("my-bucket", f"file_{i}.json")
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            
    print("\nTesting custom service...")
    for i in range(5):
        try:
            result = call_custom_service()
            print(f"  ✓ {result}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            
    # Print statistics
    manager.print_statistics()


if __name__ == "__main__":
    demo_retry_manager()