"""
Test script for suggestions update functionality.

This script tests whether suggestions are properly updated in response to user queries
and whether they correlate properly with AI responses.
"""

import uuid
import json
from agents.mcp_coordinator import MCPCoordinator
from utils.k8s_client import K8sClient
from utils.llm_client_improved import LLMClient
from utils.db_handler import DBHandler

def main():
    """Test the suggestions update functionality."""
    # Create a unique investigation ID
    investigation_id = str(uuid.uuid4())
    print(f"Test investigation ID: {investigation_id}")
    
    # Create the necessary components
    k8s_client = K8sClient()  # K8sClient automatically finds the kubeconfig
    coordinator = MCPCoordinator(k8s_client, provider="anthropic")
    db_handler = DBHandler(base_dir="logs")  # Store test data in the logs directory
    
    # Create initial investigation
    new_investigation_id = db_handler.create_investigation(
        title="Test Suggestions Update",
        namespace="default"
    )
    # Override the generated ID with our own for testing
    investigation_id = new_investigation_id
    
    # Simulate first user query
    first_query = "What's happening in my Kubernetes cluster?"
    namespace = "default"
    
    print(f"\n1. Sending first query: '{first_query}' for namespace '{namespace}'")
    
    # Process the user query with the coordinator
    response1 = coordinator.process_user_query(
        query=first_query,
        namespace=namespace,
        investigation_id=investigation_id
    )
    
    print(f"Received response with fields: {list(response1.keys())}")
    
    # Save to the database
    if 'suggestions' in response1:
        db_handler.update_next_actions(
            investigation_id=investigation_id,
            next_actions=response1['suggestions']
        )
        print(f"Number of suggestions in first response: {len(response1['suggestions'])}")
        print(f"First suggestion: {response1['suggestions'][0]['text']}")
    else:
        print("No suggestions in first response")
    
    # Retrieve the investigation from the database to see if suggestions were saved
    investigation = db_handler.get_investigation(investigation_id)
    if investigation and 'next_actions' in investigation:
        print(f"Number of suggestions saved in database: {len(investigation['next_actions'])}")
    else:
        print("No suggestions saved in database")
    
    # Simulate selecting the first suggestion (assuming it's a run_agent suggestion)
    if 'suggestions' in response1 and len(response1['suggestions']) > 0:
        selected_suggestion = response1['suggestions'][0]
        print(f"\n2. User selected suggestion: '{selected_suggestion['text']}'")
        
        # Update suggestions after selecting the first one
        response2 = coordinator.update_suggestions_after_action(
            previous_suggestions=response1['suggestions'],
            selected_suggestion_index=0,
            namespace=namespace,
            previous_findings=[] if 'key_findings' not in response1 else response1['key_findings']
        )
        
        if response2 and 'suggestions' in response2:
            print(f"Number of suggestions after update: {len(response2['suggestions'])}")
            print(f"First updated suggestion: {response2['suggestions'][0]['text']}")
            
            # Save the updated suggestions to the database
            db_handler.update_next_actions(
                investigation_id=investigation_id,
                next_actions=response2['suggestions']
            )
            
            # Verify the suggestions were updated in the database
            updated_investigation = db_handler.get_investigation(investigation_id)
            if updated_investigation and 'next_actions' in updated_investigation:
                print(f"Number of suggestions now in database: {len(updated_investigation['next_actions'])}")
                print(f"First suggestion in database: {updated_investigation['next_actions'][0]['text']}")
            else:
                print("No suggestions found in updated database entry")
        else:
            print("No suggestions in second response")
    else:
        print("No suggestions to select from first response")
    
    # Simulate a second user query to see if suggestions are updated
    second_query = "Why are my pods crashing?"
    print(f"\n3. Sending follow-up query: '{second_query}'")
    
    response3 = coordinator.process_user_query(
        query=second_query,
        namespace=namespace,
        investigation_id=investigation_id,
        previous_findings=[] if 'key_findings' not in response1 else response1['key_findings']
    )
    
    if 'suggestions' in response3:
        print(f"Number of suggestions in follow-up response: {len(response3['suggestions'])}")
        print(f"First suggestion in follow-up: {response3['suggestions'][0]['text']}")
        
        # Save to the database
        db_handler.update_next_actions(
            investigation_id=investigation_id,
            next_actions=response3['suggestions']
        )
        
        # Verify in database
        final_investigation = db_handler.get_investigation(investigation_id)
        if final_investigation and 'next_actions' in final_investigation:
            print(f"Final number of suggestions in database: {len(final_investigation['next_actions'])}")
            print(f"Final first suggestion in database: {final_investigation['next_actions'][0]['text']}")
        else:
            print("No suggestions found in final database entry")
    else:
        print("No suggestions in follow-up response")
    
    # Check correlation between response and suggestions
    if 'suggestions' in response3 and 'response' in response3:
        print("\n4. Checking correlation between response and suggestions:")
        print(f"Response snippet: {response3['response'][:100]}...")
        for i, suggestion in enumerate(response3['suggestions'][:3]):
            print(f"Suggestion {i+1}: {suggestion['text']} - Priority: {suggestion.get('priority', 'unknown')}")
            print(f"  Reasoning: {suggestion.get('reasoning', 'none provided')}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    main()