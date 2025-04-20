"""
Test script for full logging functionality

This script tests the full flow of data through the logging system, simulating
what happens when a user interacts with the system.
"""

import os
import uuid
import time
from agents.mcp_coordinator import MCPCoordinator
from utils.k8s_client import K8sClient
from utils.llm_client_improved import LLMClient

def main():
    """Test the full logging functionality."""
    # Create a unique investigation ID
    investigation_id = str(uuid.uuid4())
    print(f"Test investigation ID: {investigation_id}")
    
    # Create the necessary components
    llm_client = LLMClient(provider="anthropic")
    k8s_client = K8sClient(kubeconfig_path="/home/runner/workspace/kube-config/safe-kubeconfig.yaml")
    coordinator = MCPCoordinator(llm_client=llm_client, k8s_client=k8s_client)
    
    # Simulate a user query
    user_query = "What's wrong with my Kubernetes cluster?"
    namespace = "default"
    
    print(f"Sending query: '{user_query}' for namespace '{namespace}'")
    
    # Process the user query with the coordinator
    response = coordinator.process_user_query(
        query=user_query,
        namespace=namespace,
        investigation_id=investigation_id
    )
    
    print(f"Received response with fields: {list(response.keys())}")
    
    # Also test the summary generation
    summary_response = coordinator.generate_summary_from_query(
        query=user_query, 
        namespace=namespace,
        investigation_id=investigation_id
    )
    
    print(f"Generated summary with fields: {list(summary_response.keys())}")
    
    # Wait for logging to complete
    time.sleep(1)
    
    # Find the latest log file
    log_dir = "logs/prompts"
    log_files = [f for f in os.listdir(log_dir) if f.startswith("prompt_log_")]
    log_files.sort(reverse=True)
    
    if log_files:
        latest_log = os.path.join(log_dir, log_files[0])
        print(f"Latest log file: {latest_log}")
        
        # Check if our investigation_id appears in the log
        with open(latest_log, 'r') as f:
            log_content = f.read()
            if investigation_id in log_content:
                print(f"✅ Investigation ID found in logs")
                print("Logging is functioning correctly!")
            else:
                print(f"❌ Investigation ID not found in logs")
                print("Logging may not be working properly.")
    else:
        print("No log files found.")

if __name__ == "__main__":
    main()