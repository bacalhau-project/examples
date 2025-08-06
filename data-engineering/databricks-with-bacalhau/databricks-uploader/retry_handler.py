#!/usr/bin/env uv run -s
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "tenacity>=8.2.0",
#     "pydantic>=2.5.0"
# ]
# ///

"""
Retry Handler for Pipeline Components

Provides intelligent retry logic with:
- Exponential backoff
- Circuit breaker pattern
- Error classification
- Retry policies per error type
- Metrics and logging integration
"""

import time
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Type, Union
from functools import wraps
import logging

from tenacity import (
    retry,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_fixed,
    wait_random,
    retry_if_exception_type,
    retry_if_result,
    before_retry,
    after_retry,
    RetryError
)
from pydantic import BaseModel, Field

from pipeline_logging import get_logger


class RetryConfig(BaseModel):
    """Configuration for retry behavior."""
    max_attempts: int = Field(default=3, description="Maximum retry attempts")
    initial_wait: float = Field(default=1.0, description="Initial wait time in seconds")
    max_wait: float = Field(default=60.0, description="Maximum wait time in seconds")
    exponential_base: float = Field(default=2.0, description="Base for exponential backoff")
    jitter: bool = Field(default=True, description="Add random jitter to wait times")
    
    # Circuit breaker settings
    circuit_breaker_enabled: bool = Field(default=True)
    failure_threshold: int = Field(default=5, description="Failures before circuit opens")
    recovery_timeout: int = Field(default=60, description="Seconds before circuit recovery")
    
    # Error-specific policies
    retriable_errors: List[Type[Exception]] = Field(
        default=[
            ConnectionError,
            TimeoutError,
            IOError
        ]
    )
    
    # Logging
    log_retries: bool = Field(default=True)
    

class RetryStatistics(BaseModel):
    """Statistics for retry operations."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_retries: int = 0
    retry_success: int = 0
    retry_exhausted: int = 0
    circuit_breaker_trips: int = 0
    last_failure: Optional[datetime] = None
    last_success: Optional[datetime] = None


class CircuitBreaker:
    """Circuit breaker implementation."""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    def call_succeeded(self):
        """Record successful call."""
        self.failure_count = 0
        self.state = "closed"
        
    def call_failed(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            
    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "closed":
            return False
            
        if self.state == "open" and self.last_failure_time:
            # Check if recovery timeout has passed
            if datetime.now(timezone.utc) - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "half-open"
                return False
                
        return self.state == "open"
        
    def get_state(self) -> str:
        """Get current state."""
        return self.state


class RetryHandler:
    """Manages retry logic for pipeline operations."""
    
    def __init__(self, name: str, config: Optional[RetryConfig] = None):
        """Initialize retry handler.
        
        Args:
            name: Handler name for logging
            config: Retry configuration
        """
        self.name = name
        self.config = config or RetryConfig()
        self.logger = get_logger(f"retry_{name}")
        self.statistics = RetryStatistics()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout
        )
        
    def _before_retry_callback(self, retry_state):
        """Called before each retry attempt."""
        if self.config.log_retries:
            attempt = retry_state.attempt_number
            if hasattr(retry_state.outcome, 'exception'):
                exc = retry_state.outcome.exception()
                self.logger.warning(
                    f"Retry attempt {attempt} after error",
                    attempt=attempt,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    operation=self.name
                )
            else:
                self.logger.warning(
                    f"Retry attempt {attempt}",
                    attempt=attempt,
                    operation=self.name
                )
                
        self.statistics.total_retries += 1
        
    def _after_retry_callback(self, retry_state):
        """Called after each retry attempt."""
        if retry_state.outcome.failed:
            self.logger.debug(
                "Retry attempt failed",
                attempt=retry_state.attempt_number,
                operation=self.name
            )
            
    def _is_retriable_error(self, exception: Exception) -> bool:
        """Check if error is retriable.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if error should be retried
        """
        # Check against configured retriable errors
        for error_type in self.config.retriable_errors:
            if isinstance(exception, error_type):
                return True
                
        # Check for specific error patterns
        error_message = str(exception).lower()
        retriable_patterns = [
            "connection reset",
            "connection refused", 
            "timeout",
            "temporarily unavailable",
            "too many requests",
            "rate limit",
            "service unavailable"
        ]
        
        return any(pattern in error_message for pattern in retriable_patterns)
        
    def with_retry(self, func: Optional[Callable] = None, **custom_config):
        """Decorator to add retry logic to a function.
        
        Args:
            func: Function to wrap
            **custom_config: Override configuration for this function
            
        Returns:
            Wrapped function with retry logic
        """
        # Allow custom configuration
        config = self.config.copy()
        for key, value in custom_config.items():
            if hasattr(config, key):
                setattr(config, key, value)
                
        def decorator(f):
            # Build retry decorator
            retry_decorator = retry(
                stop=stop_after_attempt(config.max_attempts),
                wait=wait_exponential(
                    multiplier=config.initial_wait,
                    max=config.max_wait,
                    exp_base=config.exponential_base
                ) + (wait_random(0, 1) if config.jitter else wait_fixed(0)),
                retry=retry_if_exception_type(tuple(config.retriable_errors)),
                before=self._before_retry_callback,
                after=self._after_retry_callback,
                reraise=True
            )
            
            @wraps(f)
            def wrapper(*args, **kwargs):
                # Check circuit breaker
                if self.config.circuit_breaker_enabled and self.circuit_breaker.is_open():
                    self.statistics.circuit_breaker_trips += 1
                    raise RuntimeError(
                        f"Circuit breaker is open for {self.name}. "
                        f"Too many failures ({self.circuit_breaker.failure_count})"
                    )
                    
                self.statistics.total_calls += 1
                start_time = time.time()
                
                try:
                    # Apply retry logic
                    result = retry_decorator(f)(*args, **kwargs)
                    
                    # Success
                    self.statistics.successful_calls += 1
                    self.statistics.last_success = datetime.now(timezone.utc)
                    self.circuit_breaker.call_succeeded()
                    
                    # Log performance
                    duration = time.time() - start_time
                    if self.config.log_retries:
                        self.logger.log_performance(
                            f"{self.name}_with_retry",
                            duration=duration,
                            retries=0,
                            success=True
                        )
                        
                    return result
                    
                except RetryError as e:
                    # Retries exhausted
                    self.statistics.failed_calls += 1
                    self.statistics.retry_exhausted += 1
                    self.statistics.last_failure = datetime.now(timezone.utc)
                    self.circuit_breaker.call_failed()
                    
                    # Log failure
                    duration = time.time() - start_time
                    self.logger.error(
                        f"All retry attempts failed for {self.name}",
                        attempts=config.max_attempts,
                        duration=duration,
                        final_error=str(e.last_attempt.exception())
                    )
                    
                    # Re-raise the last exception
                    raise e.last_attempt.exception()
                    
                except Exception as e:
                    # Unexpected error
                    self.statistics.failed_calls += 1
                    self.statistics.last_failure = datetime.now(timezone.utc)
                    self.circuit_breaker.call_failed()
                    
                    self.logger.error(
                        f"Unexpected error in {self.name}",
                        error_type=type(e).__name__,
                        error_message=str(e)
                    )
                    raise
                    
            return wrapper
            
        if func is None:
            return decorator
        else:
            return decorator(func)
            
    def get_statistics(self) -> Dict[str, Any]:
        """Get retry statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = self.statistics.dict()
        stats["circuit_breaker_state"] = self.circuit_breaker.get_state()
        stats["success_rate"] = (
            self.statistics.successful_calls / self.statistics.total_calls
            if self.statistics.total_calls > 0 else 0
        )
        return stats
        
    def reset_statistics(self):
        """Reset statistics."""
        self.statistics = RetryStatistics()
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout
        )


# Predefined retry handlers for common operations
class RetryHandlers:
    """Collection of pre-configured retry handlers."""
    
    @staticmethod
    def database_handler() -> RetryHandler:
        """Retry handler for database operations."""
        config = RetryConfig(
            max_attempts=5,
            initial_wait=0.5,
            max_wait=30,
            retriable_errors=[
                ConnectionError,
                TimeoutError,
                IOError,
            ]
        )
        return RetryHandler("database", config)
        
    @staticmethod
    def s3_handler() -> RetryHandler:
        """Retry handler for S3 operations."""
        config = RetryConfig(
            max_attempts=3,
            initial_wait=1.0,
            max_wait=60,
            exponential_base=2,
            retriable_errors=[
                ConnectionError,
                TimeoutError,
                IOError,
            ]
        )
        return RetryHandler("s3", config)
        
    @staticmethod
    def databricks_handler() -> RetryHandler:
        """Retry handler for Databricks operations."""
        config = RetryConfig(
            max_attempts=5,
            initial_wait=2.0,
            max_wait=120,
            circuit_breaker_enabled=True,
            failure_threshold=3,
            recovery_timeout=300  # 5 minutes
        )
        return RetryHandler("databricks", config)
        
    @staticmethod
    def api_handler() -> RetryHandler:
        """Retry handler for API calls."""
        config = RetryConfig(
            max_attempts=3,
            initial_wait=1.0,
            max_wait=30,
            jitter=True,
            retriable_errors=[
                ConnectionError,
                TimeoutError,
                IOError,
            ]
        )
        return RetryHandler("api", config)


def demo_retry_logic():
    """Demonstrate retry functionality."""
    print("\n=== Retry Handler Demo ===\n")
    
    # Create a retry handler
    handler = RetryHandler("demo", RetryConfig(
        max_attempts=3,
        initial_wait=1,
        log_retries=True
    ))
    
    # Simulate a flaky operation
    attempt_count = 0
    
    @handler.with_retry
    def flaky_operation():
        nonlocal attempt_count
        attempt_count += 1
        
        print(f"Attempt {attempt_count}")
        
        if attempt_count < 3:
            raise ConnectionError("Connection failed")
        
        return "Success!"
        
    # Test retry logic
    try:
        result = flaky_operation()
        print(f"\nOperation succeeded: {result}")
    except Exception as e:
        print(f"\nOperation failed: {e}")
        
    # Print statistics
    stats = handler.get_statistics()
    print(f"\nRetry Statistics:")
    print(f"  Total calls: {stats['total_calls']}")
    print(f"  Successful: {stats['successful_calls']}")
    print(f"  Failed: {stats['failed_calls']}")
    print(f"  Total retries: {stats['total_retries']}")
    print(f"  Success rate: {stats['success_rate']:.2%}")
    
    # Demo circuit breaker
    print("\n\n=== Circuit Breaker Demo ===\n")
    
    cb_handler = RetryHandler("circuit_demo", RetryConfig(
        max_attempts=2,
        circuit_breaker_enabled=True,
        failure_threshold=2,
        recovery_timeout=5
    ))
    
    @cb_handler.with_retry
    def always_fails():
        raise ConnectionError("Service unavailable")
        
    # Trigger circuit breaker
    for i in range(3):
        try:
            always_fails()
        except Exception as e:
            print(f"Call {i+1} failed: {type(e).__name__}: {e}")
            
    print(f"\nCircuit breaker state: {cb_handler.circuit_breaker.get_state()}")
    
    # Try again (should fail immediately)
    try:
        always_fails()
    except RuntimeError as e:
        print(f"\nCircuit breaker prevented call: {e}")


if __name__ == "__main__":
    demo_retry_logic()