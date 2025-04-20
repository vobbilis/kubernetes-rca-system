"""
Prompt Logger for the Kubernetes Root Cause Analysis System

This module provides functionality to log prompts, responses, and context
to help with debugging, analysis, and system improvement.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, List, Union

class PromptLogger:
    """
    Logger class for tracking prompts, responses, and context in the LLM-based
    investigation system.
    """
    
    def __init__(self, log_dir: str = 'logs/prompts', 
                 log_level: int = logging.INFO):
        """
        Initialize the prompt logger.
        
        Args:
            log_dir: Directory to store log files
            log_level: Logging level
        """
        self.log_dir = log_dir
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure logger
        self.logger = logging.getLogger("prompt_logger")
        self.logger.setLevel(log_level)
        
        # Use a unique filename based on timestamp
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        self.log_file = os.path.join(log_dir, f"prompt_log_{timestamp}.jsonl")
        
        # Create a file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(log_level)
        
        # Set formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        self.logger.info(f"Initialized prompt logger. Logs will be written to {self.log_file}")
        
    def log_interaction(self, 
                      user_query: str,
                      prompt: str, 
                      response: Union[str, Dict[str, Any]], 
                      investigation_id: Optional[str] = None,
                      accumulated_findings: Optional[List[str]] = None,
                      namespace: Optional[str] = None,
                      additional_context: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a complete interaction including the user query, prompt, response, and context.
        
        Args:
            user_query: The original user query
            prompt: The prompt sent to the LLM
            response: The response received from the LLM
            investigation_id: ID of the current investigation if available
            accumulated_findings: List of accumulated findings from previous interactions
            namespace: Kubernetes namespace context
            additional_context: Any additional context information to log
        """
        # Create a log entry as a dictionary
        log_entry = {
            "timestamp": time.time(),
            "formatted_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "investigation_id": investigation_id,
            "user_query": user_query,
            "prompt": prompt,
            "response": response,
            "namespace": namespace,
            "accumulated_findings": accumulated_findings,
        }
        
        # Add any additional context
        if additional_context:
            log_entry["additional_context"] = additional_context
            
        # Write to log file as a JSON line
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            self.logger.info(f"Logged interaction for investigation {investigation_id}")
        except Exception as e:
            self.logger.error(f"Failed to log interaction: {str(e)}")
    
    def log_system_event(self, event_type: str, description: str, 
                        details: Optional[Dict[str, Any]] = None) -> None:
        """
        Log a system event, such as initialization or error.
        
        Args:
            event_type: Type of event (e.g., 'initialization', 'error')
            description: Description of the event
            details: Additional details about the event
        """
        log_entry = {
            "timestamp": time.time(),
            "formatted_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "event_type": event_type,
            "description": description,
            "details": details or {}
        }
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
            
            self.logger.info(f"Logged system event: {event_type}")
        except Exception as e:
            self.logger.error(f"Failed to log system event: {str(e)}")

# Initialize a global logger instance
prompt_logger = None

def get_logger(log_dir: str = 'logs/prompts') -> PromptLogger:
    """
    Get the global logger instance, creating it if necessary.
    
    Args:
        log_dir: Directory to store log files
        
    Returns:
        PromptLogger instance
    """
    global prompt_logger
    if prompt_logger is None:
        prompt_logger = PromptLogger(log_dir=log_dir)
    return prompt_logger