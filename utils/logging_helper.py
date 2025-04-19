import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EvidenceLogger:
    """
    Helper class for logging evidence and hypothesis information to files.
    """
    
    def __init__(self, logs_dir="logs"):
        """
        Initialize the evidence logger.
        
        Args:
            logs_dir: Directory to store logs (default: 'logs')
        """
        self.logs_dir = logs_dir
        
        # Create logs directory if it doesn't exist
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            logger.info(f"Created logs directory: {logs_dir}")
    
    def log_hypothesis(self, component: str, finding: Dict[str, Any], 
                      hypothesis: Dict[str, Any], evidence: Optional[Dict[str, Any]] = None) -> str:
        """
        Log a hypothesis and any associated evidence to a file.
        
        Args:
            component: The Kubernetes component being investigated
            finding: The finding that triggered the investigation
            hypothesis: The hypothesis being tested
            evidence: Any evidence supporting or refuting the hypothesis (optional)
            
        Returns:
            Path to the log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        component_safe = component.replace('/', '_').replace(' ', '_')
        
        # Create a unique filename
        filename = f"{timestamp}_{component_safe}_hypothesis.json"
        filepath = os.path.join(self.logs_dir, filename)
        
        # Prepare data to log
        log_data = {
            "timestamp": timestamp,
            "component": component,
            "finding": finding,
            "hypothesis": hypothesis,
            "evidence": evidence or {},
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"Logged hypothesis for {component} to {filepath}")
        return filepath
    
    def log_investigation_step(self, component: str, hypothesis: Dict[str, Any], 
                              step: Dict[str, Any], result: Dict[str, Any]) -> str:
        """
        Log an investigation step and its results.
        
        Args:
            component: The Kubernetes component being investigated
            hypothesis: The hypothesis being tested
            step: The investigation step that was executed
            result: The result of the investigation step
            
        Returns:
            Path to the log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        component_safe = component.replace('/', '_').replace(' ', '_')
        step_desc = step.get('description', 'unknown_step').replace(' ', '_')[:30]
        
        # Create a unique filename
        filename = f"{timestamp}_{component_safe}_{step_desc}.json"
        filepath = os.path.join(self.logs_dir, filename)
        
        # Prepare data to log
        log_data = {
            "timestamp": timestamp,
            "component": component,
            "hypothesis": hypothesis,
            "investigation_step": step,
            "result": result
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"Logged investigation step for {component} to {filepath}")
        return filepath
    
    def log_conclusion(self, component: str, hypothesis: Dict[str, Any], 
                       conclusion: Dict[str, Any], evidence_paths: List[str]) -> str:
        """
        Log the conclusion of an investigation.
        
        Args:
            component: The Kubernetes component being investigated
            hypothesis: The hypothesis that was tested
            conclusion: The conclusion reached
            evidence_paths: Paths to evidence files that support this conclusion
            
        Returns:
            Path to the log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        component_safe = component.replace('/', '_').replace(' ', '_')
        
        # Create a unique filename
        filename = f"{timestamp}_{component_safe}_conclusion.json"
        filepath = os.path.join(self.logs_dir, filename)
        
        # Prepare data to log
        log_data = {
            "timestamp": timestamp,
            "component": component,
            "hypothesis": hypothesis,
            "conclusion": conclusion,
            "evidence_files": evidence_paths
        }
        
        # Write to file
        with open(filepath, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"Logged conclusion for {component} to {filepath}")
        return filepath
    
    def get_evidence_for_hypothesis(self, component: str, hypothesis_desc: str) -> List[Dict[str, Any]]:
        """
        Retrieve all evidence files related to a specific hypothesis.
        
        Args:
            component: The Kubernetes component being investigated
            hypothesis_desc: Description of the hypothesis
            
        Returns:
            List of evidence data from log files
        """
        component_safe = component.replace('/', '_').replace(' ', '_')
        evidence_list = []
        
        # Look for relevant files in the logs directory
        for filename in os.listdir(self.logs_dir):
            if component_safe in filename:
                filepath = os.path.join(self.logs_dir, filename)
                
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        
                    # Check if this file is relevant to the hypothesis
                    stored_hypothesis = data.get('hypothesis', {})
                    if stored_hypothesis.get('description', '') == hypothesis_desc:
                        evidence_list.append(data)
                except Exception as e:
                    logger.error(f"Error reading log file {filepath}: {e}")
        
        return evidence_list