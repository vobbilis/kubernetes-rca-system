"""
Test script for prompt_logger.py

This script tests the functionality of the prompt logger to ensure it works correctly.
"""

import time
import os
from utils.prompt_logger import get_logger

def main():
    """Test the prompt logger."""
    # Get the logger
    logger = get_logger()
    
    # Test logging an interaction
    logger.log_interaction(
        user_query="What's wrong with my Kubernetes cluster?",
        prompt="Please analyze the Kubernetes cluster state",
        response="There appear to be several issues with your cluster",
        investigation_id="test-investigation-id",
        accumulated_findings=["Finding 1", "Finding 2"],
        namespace="default",
        additional_context={"model": "test-model", "temperature": 0.2}
    )
    
    # Test logging a system event
    logger.log_system_event(
        event_type="test",
        description="Test event",
        details={"test_key": "test_value"}
    )
    
    print(f"Logged test entries to: {logger.log_file}")
    print("Contents of log file:")
    
    # Wait for write to complete
    time.sleep(0.5)
    
    # Read and print the file
    with open(logger.log_file, 'r') as f:
        print(f.read())

if __name__ == "__main__":
    main()