import json
import os
import time
import uuid
from typing import Dict, List, Optional, Any
import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

class DBHandler:
    """
    Handles persistence of investigations using JSON files.
    Each investigation is stored in its own file with a unique ID.
    """

    def __init__(self, base_dir: str = LOGS_DIR):
        """
        Initialize the database handler.
        
        Args:
            base_dir: Directory to store the investigation data
        """
        self.base_dir = base_dir
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
    
    def create_investigation(self, title: str, namespace: str, context: Optional[str] = None) -> str:
        """
        Create a new investigation record.
        
        Args:
            title: Title of the investigation
            namespace: Kubernetes namespace being investigated
            context: Optional context information for the investigation
            
        Returns:
            investigation_id: Unique identifier for the investigation
        """
        investigation_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        print(f"DEBUG: Creating investigation with title: {title}, namespace: {namespace}")
        print(f"DEBUG: Generated investigation ID: {investigation_id}")
        
        investigation_data = {
            "id": investigation_id,
            "title": title,
            "namespace": namespace,
            "context": context,
            "created_at": timestamp,
            "updated_at": timestamp,
            "summary": "",
            "status": "in_progress",
            "conversation": [],
            "evidence": {},
            "agent_findings": {},
            "next_actions": [],
            "accumulated_findings": []  # Initialize accumulated findings
        }
        
        # Save the investigation
        success = self._save_investigation(investigation_data)
        
        if success:
            print(f"DEBUG: Successfully saved investigation {investigation_id}")
        else:
            print(f"DEBUG: Failed to save investigation {investigation_id}")
            
        return investigation_id
    
    def update_investigation(self, investigation_id: str, 
                            updates: Dict[str, Any]) -> bool:
        """
        Update an existing investigation.
        
        Args:
            investigation_id: ID of the investigation to update
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation = self.get_investigation(investigation_id)
        if not investigation:
            return False
        
        # Ensure accumulated_findings exists for older investigations
        if "accumulated_findings" not in investigation:
            investigation["accumulated_findings"] = []
            
        # Update the investigation data
        for key, value in updates.items():
            # Special case for accumulated_findings to handle upgrading older records
            if key == "accumulated_findings" or key in investigation:
                investigation[key] = value
        
        # Update the timestamp
        investigation["updated_at"] = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save the updated investigation
        self._save_investigation(investigation)
        
        return True
    
    def add_conversation_entry(self, investigation_id: str, 
                              role: str, content: str) -> bool:
        """
        Add an entry to the conversation history of an investigation.
        
        Args:
            investigation_id: ID of the investigation
            role: Role of the speaker (user, system, assistant)
            content: Content of the message
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation = self.get_investigation(investigation_id)
        if not investigation:
            return False
        
        # Add the conversation entry
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        if "conversation" not in investigation:
            investigation["conversation"] = []
        
        investigation["conversation"].append(entry)
        
        # Update the investigation
        return self.update_investigation(investigation_id, {
            "conversation": investigation["conversation"]
        })
    
    def add_evidence(self, investigation_id: str, 
                     evidence_type: str, evidence_data: Any) -> bool:
        """
        Add evidence to an investigation.
        
        Args:
            investigation_id: ID of the investigation
            evidence_type: Type of evidence (logs, metrics, events, etc.)
            evidence_data: Evidence data
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation = self.get_investigation(investigation_id)
        if not investigation:
            return False
        
        if "evidence" not in investigation:
            investigation["evidence"] = {}
        
        # Add timestamp to evidence
        evidence_entry = {
            "data": evidence_data,
            "timestamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        if evidence_type not in investigation["evidence"]:
            investigation["evidence"][evidence_type] = []
        
        investigation["evidence"][evidence_type].append(evidence_entry)
        
        # Update the investigation
        return self.update_investigation(investigation_id, {
            "evidence": investigation["evidence"]
        })
    
    def add_agent_findings(self, investigation_id: str, 
                          agent_type: str, findings: Dict[str, Any]) -> bool:
        """
        Add agent findings to an investigation.
        
        Args:
            investigation_id: ID of the investigation
            agent_type: Type of agent (logs, metrics, events, etc.)
            findings: Agent findings
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation = self.get_investigation(investigation_id)
        if not investigation:
            return False
        
        if "agent_findings" not in investigation:
            investigation["agent_findings"] = {}
        
        # Add timestamp to findings
        findings_entry = {
            "data": findings,
            "timestamp": datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        investigation["agent_findings"][agent_type] = findings_entry
        
        # Update the investigation
        return self.update_investigation(investigation_id, {
            "agent_findings": investigation["agent_findings"]
        })
    
    def update_next_actions(self, investigation_id: str, 
                           next_actions: List[Dict[str, Any]]) -> bool:
        """
        Update the next actions for an investigation.
        
        Args:
            investigation_id: ID of the investigation
            next_actions: List of next action suggestions
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation = self.get_investigation(investigation_id)
        if not investigation:
            return False
        
        # Update the next actions
        investigation["next_actions"] = next_actions
        
        # Update the investigation
        return self.update_investigation(investigation_id, {
            "next_actions": next_actions
        })
    
    def update_summary(self, investigation_id: str, summary: str) -> bool:
        """
        Update the summary of an investigation.
        
        Args:
            investigation_id: ID of the investigation
            summary: New summary text
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_investigation(investigation_id, {"summary": summary})
    
    def mark_investigation_completed(self, investigation_id: str) -> bool:
        """
        Mark an investigation as completed.
        
        Args:
            investigation_id: ID of the investigation
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_investigation(investigation_id, {"status": "completed"})
    
    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an investigation by ID.
        
        Args:
            investigation_id: ID of the investigation
            
        Returns:
            dict: Investigation data, or None if not found
        """
        file_path = os.path.join(self.base_dir, f"{investigation_id}.json")
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading investigation {investigation_id}: {e}")
            return None
    
    def list_investigations(self) -> List[Dict[str, Any]]:
        """
        List all investigations.
        
        Returns:
            list: List of investigation metadata
        """
        investigations = []
        
        for filename in os.listdir(self.base_dir):
            if filename.endswith('.json') and not filename.endswith('_hypothesis.json'):
                file_path = os.path.join(self.base_dir, filename)
                try:
                    with open(file_path, 'r') as f:
                        investigation = json.load(f)
                        # Include only the metadata for listing
                        investigations.append({
                            "id": investigation.get("id", "unknown"),
                            "title": investigation.get("title", "Untitled Investigation"),
                            "namespace": investigation.get("namespace", "unknown"),
                            "created_at": investigation.get("created_at", ""),
                            "updated_at": investigation.get("updated_at", ""),
                            "status": investigation.get("status", "unknown"),
                            "summary": investigation.get("summary", "")
                        })
                except Exception as e:
                    print(f"Error reading investigation file {filename}: {e}")
        
        # Sort by updated_at in descending order (most recent first)
        # Use a safe sorting method that handles None values
        def safe_sort_key(x):
            updated_at = x.get("updated_at")
            if not updated_at:
                return ""
            return updated_at
        
        investigations.sort(key=safe_sort_key, reverse=True)
        
        return investigations
    
    def save_hypothesis(self, investigation_id: str, hypothesis: Dict[str, Any]) -> bool:
        """
        Save a hypothesis for an investigation.
        
        Args:
            investigation_id: ID of the investigation
            hypothesis: Hypothesis data
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Add timestamp if not present
        if "timestamp" not in hypothesis:
            hypothesis["timestamp"] = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate a filename for the hypothesis
        hypothesis_id = hypothesis.get("id", str(uuid.uuid4()))
        timestamp = hypothesis.get("timestamp")
        component_type = hypothesis.get("component_type", "Unknown")
        component_name = hypothesis.get("component_name", "unknown")
        
        filename = f"{timestamp}_{component_type}_{component_name}_hypothesis.json"
        file_path = os.path.join(self.base_dir, filename)
        
        try:
            with open(file_path, 'w') as f:
                json.dump(hypothesis, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving hypothesis: {e}")
            return False
    
    def _save_investigation(self, investigation: Dict[str, Any]) -> bool:
        """
        Save an investigation to a file.
        
        Args:
            investigation: Investigation data
            
        Returns:
            bool: True if successful, False otherwise
        """
        investigation_id = investigation.get("id")
        if not investigation_id:
            print(f"ERROR [db_handler.py]: Cannot save investigation - missing ID")
            return False
        
        file_path = os.path.join(self.base_dir, f"{investigation_id}.json")
        print(f"DEBUG [db_handler.py]: Saving investigation to {file_path}")
        
        try:
            # Check permissions on the logs directory
            if os.path.exists(self.base_dir):
                # Check if we have write permissions
                test_permissions = os.access(self.base_dir, os.W_OK)
                print(f"DEBUG [db_handler.py]: Write permissions for {self.base_dir}: {test_permissions}")
            
            # Ensure logs directory exists
            if not os.path.exists(self.base_dir):
                print(f"DEBUG [db_handler.py]: Creating logs directory {self.base_dir}")
                os.makedirs(self.base_dir)
                
                # Verify the directory was created
                if not os.path.exists(self.base_dir):
                    print(f"ERROR [db_handler.py]: Failed to create directory {self.base_dir}")
                    return False
            
            # Write a test file to verify file system is working
            test_file = os.path.join(self.base_dir, f"test_{time.time()}.tmp")
            try:
                with open(test_file, 'w') as tf:
                    tf.write("test")
                os.remove(test_file)
                print(f"DEBUG [db_handler.py]: Successfully wrote and deleted test file")
            except Exception as te:
                print(f"ERROR [db_handler.py]: Failed to write test file: {str(te)}")
                return False
            
            # Now save the actual investigation file
            with open(file_path, 'w') as f:
                json.dump(investigation, f, indent=2)
            print(f"DEBUG [db_handler.py]: Successfully wrote investigation file")
            
            # Verify the file was created
            if os.path.exists(file_path):
                # Verify file has content
                file_size = os.path.getsize(file_path)
                print(f"DEBUG [db_handler.py]: Verified file exists: {file_path}, size: {file_size} bytes")
                
                # Try to read it back to make sure it's valid JSON
                try:
                    with open(file_path, 'r') as f:
                        test_read = json.load(f)
                    print(f"DEBUG [db_handler.py]: Successfully read back the file as valid JSON")
                    return True
                except Exception as je:
                    print(f"ERROR [db_handler.py]: File was created but contains invalid JSON: {str(je)}")
                    return False
            else:
                print(f"ERROR [db_handler.py]: File not found after write: {file_path}")
                return False
        except Exception as e:
            print(f"ERROR [db_handler.py]: Failed to save investigation {investigation_id}: {str(e)}")
            return False