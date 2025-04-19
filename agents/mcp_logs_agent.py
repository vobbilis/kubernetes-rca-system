from typing import Dict, List, Any
from agents.mcp_agent import MCPAgent

class MCPLogsAgent(MCPAgent):
    """
    Logs agent using the Model Context Protocol.
    Specializes in analyzing Kubernetes logs data to identify application and system issues.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the logs agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        super().__init__(k8s_client, provider)
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this logs agent.
        
        Returns:
            List of tool definitions
        """
        # Get base tools
        tools = super()._get_agent_tools()
        
        # Add logs-specific tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "get_pod_logs",
                    "description": "Get logs for a specific pod",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "pod_name": {
                                "type": "string",
                                "description": "Name of the pod"
                            },
                            "container_name": {
                                "type": "string",
                                "description": "Name of the container (optional)",
                                "default": ""
                            },
                            "tail_lines": {
                                "type": "integer",
                                "description": "Number of lines to return from the end of the logs",
                                "default": 100
                            }
                        },
                        "required": ["namespace", "pod_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_previous_pod_logs",
                    "description": "Get logs from the previous instance of a pod (if it was restarted)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "pod_name": {
                                "type": "string",
                                "description": "Name of the pod"
                            },
                            "container_name": {
                                "type": "string",
                                "description": "Name of the container (optional)",
                                "default": ""
                            }
                        },
                        "required": ["namespace", "pod_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_pod_status",
                    "description": "Get detailed status for a specific pod",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "pod_name": {
                                "type": "string",
                                "description": "Name of the pod"
                            }
                        },
                        "required": ["namespace", "pod_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_logs_for_pattern",
                    "description": "Search logs across pods for a specific pattern",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "pattern": {
                                "type": "string",
                                "description": "Pattern to search for (case-sensitive)"
                            },
                            "pod_prefix": {
                                "type": "string",
                                "description": "Optional pod name prefix to filter by",
                                "default": ""
                            }
                        },
                        "required": ["namespace", "pattern"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_container_state",
                    "description": "Analyze the state of containers in a pod",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "pod_name": {
                                "type": "string",
                                "description": "Name of the pod"
                            }
                        },
                        "required": ["namespace", "pod_name"]
                    }
                }
            }
        ])
        
        return tools
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the logs agent.
        
        Returns:
            String containing the system prompt
        """
        return """You are a Kubernetes Logs Expert Agent. Your specialty is analyzing logs and container 
states to identify application errors, crashes, and operational issues in Kubernetes clusters.

Your responsibilities:
1. Analyze logs from pods and containers to identify errors and issues
2. Examine container states to detect crashes, restarts, and unhealthy conditions
3. Look for patterns in logs that indicate application problems
4. Identify common error types such as configuration issues, connection failures, or resource constraints
5. Correlate log messages with pod status and container states
6. Detect issues with init containers, sidecars, and main application containers

When analyzing:
- Look for ERROR, WARN, or FATAL messages in the logs
- Identify frequent restarts or crash loops
- Check for connection failures to external services
- Look for permission or authentication issues
- Identify out of memory errors or resource constraints
- Check for issues with application initialization or startup
- Analyze termination reason codes and exit statuses

Provide clear, evidence-based findings with:
- Component: The specific pod/container affected
- Issue: A clear description of the problem
- Severity: Critical, High, Medium, Low, or Info
- Evidence: Log messages and container states supporting the finding
- Recommendation: Specific actions to resolve the issue

Use all available tools to gather comprehensive logs data before making your assessment.
Think step-by-step and be thorough in your analysis.
"""
    
    def _tool_get_pod_logs(self, arguments: Dict[str, Any]) -> str:
        """
        Tool implementation: Get logs for a specific pod.
        
        Args:
            arguments: Arguments containing namespace, pod_name, and optional parameters
            
        Returns:
            String containing the pod logs
        """
        namespace = arguments["namespace"]
        pod_name = arguments["pod_name"]
        container_name = arguments.get("container_name", "")
        tail_lines = arguments.get("tail_lines", 100)
        
        return self.k8s_client.get_pod_logs(
            namespace=namespace,
            pod_name=pod_name,
            container_name=container_name,
            tail_lines=tail_lines
        )
    
    def _tool_get_previous_pod_logs(self, arguments: Dict[str, Any]) -> str:
        """
        Tool implementation: Get logs from the previous instance of a pod.
        
        Args:
            arguments: Arguments containing namespace, pod_name, and optional container_name
            
        Returns:
            String containing the previous pod logs
        """
        namespace = arguments["namespace"]
        pod_name = arguments["pod_name"]
        container_name = arguments.get("container_name", "")
        
        return self.k8s_client.get_pod_logs(
            namespace=namespace,
            pod_name=pod_name,
            container_name=container_name,
            previous=True
        )
    
    def _tool_get_pod_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get detailed status for a specific pod.
        
        Args:
            arguments: Arguments containing namespace and pod_name
            
        Returns:
            Dictionary containing the pod status
        """
        namespace = arguments["namespace"]
        pod_name = arguments["pod_name"]
        
        return self.k8s_client.get_pod_status(namespace, pod_name)
    
    def _tool_search_logs_for_pattern(self, arguments: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Tool implementation: Search logs across pods for a specific pattern.
        
        Args:
            arguments: Arguments containing namespace, pattern, and optional pod_prefix
            
        Returns:
            Dictionary mapping pod names to lists of matching log lines
        """
        namespace = arguments["namespace"]
        pattern = arguments["pattern"]
        pod_prefix = arguments.get("pod_prefix", "")
        
        # Get list of pods
        pods = self.k8s_client.get_pods(namespace)
        
        # Filter pods by prefix if specified
        if pod_prefix:
            pods = [pod for pod in pods if pod["metadata"]["name"].startswith(pod_prefix)]
        
        # Search logs for each pod
        results = {}
        for pod in pods:
            pod_name = pod["metadata"]["name"]
            try:
                logs = self.k8s_client.get_pod_logs(namespace, pod_name)
                matching_lines = []
                
                for line in logs.split('\n'):
                    if pattern in line:
                        matching_lines.append(line)
                
                if matching_lines:
                    results[pod_name] = matching_lines
            except Exception as e:
                results[pod_name] = [f"Error retrieving logs: {str(e)}"]
        
        return results
    
    def _tool_analyze_container_state(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Analyze the state of containers in a pod.
        
        Args:
            arguments: Arguments containing namespace and pod_name
            
        Returns:
            Dictionary with container state analysis
        """
        namespace = arguments["namespace"]
        pod_name = arguments["pod_name"]
        
        # Get pod status
        pod = self.k8s_client.get_pod_status(namespace, pod_name)
        
        if not pod:
            return {"error": f"Pod {pod_name} not found in namespace {namespace}"}
        
        # Initialize results
        result = {
            "pod_name": pod_name,
            "phase": pod.get("status", {}).get("phase", "Unknown"),
            "containers": {},
            "init_containers": {},
            "restarts": 0,
            "issues": []
        }
        
        # Process container statuses
        container_statuses = pod.get("status", {}).get("containerStatuses", [])
        for status in container_statuses:
            container_name = status.get("name", "unknown")
            ready = status.get("ready", False)
            restarts = status.get("restartCount", 0)
            result["restarts"] += restarts
            
            state = status.get("state", {})
            last_state = status.get("lastState", {})
            
            container_result = {
                "ready": ready,
                "restarts": restarts,
                "current_state": list(state.keys())[0] if state else "unknown",
                "last_state": list(last_state.keys())[0] if last_state else "none"
            }
            
            # Add detailed state information
            if "waiting" in state:
                container_result["waiting_reason"] = state["waiting"].get("reason", "")
                container_result["waiting_message"] = state["waiting"].get("message", "")
                
                # Check for common issues
                reason = state["waiting"].get("reason", "")
                if reason == "CrashLoopBackOff":
                    result["issues"].append({
                        "container": container_name,
                        "issue": "Container is crash looping",
                        "details": state["waiting"].get("message", "")
                    })
                elif reason == "ImagePullBackOff" or reason == "ErrImagePull":
                    result["issues"].append({
                        "container": container_name,
                        "issue": "Failed to pull container image",
                        "details": state["waiting"].get("message", "")
                    })
                elif reason == "CreateContainerConfigError":
                    result["issues"].append({
                        "container": container_name,
                        "issue": "Error in container configuration",
                        "details": state["waiting"].get("message", "")
                    })
            
            if "terminated" in state:
                container_result["exit_code"] = state["terminated"].get("exitCode", 0)
                container_result["termination_reason"] = state["terminated"].get("reason", "")
                container_result["termination_message"] = state["terminated"].get("message", "")
                
                # Check for termination issues
                if state["terminated"].get("exitCode", 0) != 0:
                    result["issues"].append({
                        "container": container_name,
                        "issue": f"Container terminated with non-zero exit code: {state['terminated'].get('exitCode', 0)}",
                        "details": state["terminated"].get("message", "No details provided")
                    })
            
            if "terminated" in last_state:
                container_result["last_exit_code"] = last_state["terminated"].get("exitCode", 0)
                container_result["last_termination_reason"] = last_state["terminated"].get("reason", "")
                
                # Check for frequent restarts with errors
                if restarts > 3 and last_state["terminated"].get("exitCode", 0) != 0:
                    result["issues"].append({
                        "container": container_name,
                        "issue": f"Container has restarted {restarts} times with errors",
                        "details": f"Last exit code: {last_state['terminated'].get('exitCode', 0)}"
                    })
            
            result["containers"][container_name] = container_result
        
        # Process init container statuses
        init_container_statuses = pod.get("status", {}).get("initContainerStatuses", [])
        for status in init_container_statuses:
            container_name = status.get("name", "unknown")
            ready = status.get("ready", False)
            restarts = status.get("restartCount", 0)
            
            state = status.get("state", {})
            last_state = status.get("lastState", {})
            
            container_result = {
                "ready": ready,
                "restarts": restarts,
                "current_state": list(state.keys())[0] if state else "unknown",
                "last_state": list(last_state.keys())[0] if last_state else "none"
            }
            
            # Add detailed state information for init containers
            if "waiting" in state:
                container_result["waiting_reason"] = state["waiting"].get("reason", "")
                
                # Check for init container issues
                reason = state["waiting"].get("reason", "")
                if reason in ["CrashLoopBackOff", "Error"]:
                    result["issues"].append({
                        "container": f"init:{container_name}",
                        "issue": "Init container is failing",
                        "details": state["waiting"].get("message", "")
                    })
            
            if "terminated" in state:
                container_result["exit_code"] = state["terminated"].get("exitCode", 0)
                
                # Check for init container termination issues
                if state["terminated"].get("exitCode", 0) != 0:
                    result["issues"].append({
                        "container": f"init:{container_name}",
                        "issue": f"Init container terminated with non-zero exit code: {state['terminated'].get('exitCode', 0)}",
                        "details": state["terminated"].get("message", "No details provided")
                    })
            
            result["init_containers"][container_name] = container_result
        
        # Check for pod-level issues
        conditions = pod.get("status", {}).get("conditions", [])
        for condition in conditions:
            if condition.get("type") == "PodScheduled" and condition.get("status") != "True":
                result["issues"].append({
                    "container": "pod",
                    "issue": "Pod scheduling issues",
                    "details": condition.get("message", "")
                })
            elif condition.get("type") == "Initialized" and condition.get("status") != "True":
                result["issues"].append({
                    "container": "pod",
                    "issue": "Pod initialization issues",
                    "details": condition.get("message", "")
                })
            elif condition.get("type") == "Ready" and condition.get("status") != "True":
                result["issues"].append({
                    "container": "pod",
                    "issue": "Pod not ready",
                    "details": condition.get("message", "")
                })
        
        return result