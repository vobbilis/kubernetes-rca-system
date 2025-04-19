from typing import Dict, List, Any
from agents.mcp_agent import MCPAgent

class MCPEventsAgent(MCPAgent):
    """
    Events agent using the Model Context Protocol.
    Specializes in analyzing Kubernetes events to identify control plane and operational issues.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the events agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        super().__init__(k8s_client, provider)
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this events agent.
        
        Returns:
            List of tool definitions
        """
        # Get base tools
        tools = super()._get_agent_tools()
        
        # Add events-specific tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "get_namespace_events",
                    "description": "Get events for a specific namespace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            }
                        },
                        "required": ["namespace"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resource_events",
                    "description": "Get events for a specific resource",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "resource_type": {
                                "type": "string",
                                "description": "Type of resource (pod, deployment, service, etc.)"
                            },
                            "resource_name": {
                                "type": "string",
                                "description": "Name of the resource"
                            }
                        },
                        "required": ["namespace", "resource_type", "resource_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_cluster_events",
                    "description": "Get cluster-wide events",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "field_selector": {
                                "type": "string",
                                "description": "Field selector for filtering events (optional)",
                                "default": ""
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of events to return",
                                "default": 50
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_events_by_type",
                    "description": "Filter events by event type",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "event_type": {
                                "type": "string",
                                "description": "Type of event to filter by (Warning, Normal, etc.)"
                            }
                        },
                        "required": ["namespace", "event_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "filter_events_by_reason",
                    "description": "Filter events by reason",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason to filter by (FailedScheduling, Killing, Created, etc.)"
                            }
                        },
                        "required": ["namespace", "reason"]
                    }
                }
            }
        ])
        
        return tools
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the events agent.
        
        Returns:
            String containing the system prompt
        """
        return """You are a Kubernetes Events Expert Agent. Your specialty is analyzing Kubernetes events 
to identify cluster operations issues, scheduling problems, and resource lifecycle events.

Your responsibilities:
1. Analyze Kubernetes events to identify operational issues 
2. Look for patterns in events that indicate systemic problems
3. Identify scheduling failures, node issues, and resource conflicts
4. Detect failed operations, throttling, and API server errors
5. Find volume-related issues and networking problems
6. Analyze the frequency and timing of events to identify recurring problems

When analyzing:
- Look for Warning events, which often indicate problems
- Identify frequent occurrences of the same event type
- Check for FailedScheduling events and their reasons
- Look for unusual termination or creation patterns
- Identify volume attachment or mounting issues
- Check for node-related events like NodeNotReady
- Look for network policy or service endpoint issues
- Pay attention to resource quota or limits issues

Common event reasons to investigate:
- FailedScheduling: Pods cannot be scheduled to nodes
- FailedMount: Volume mounting issues
- Unhealthy: Failed health checks
- NodeNotReady: Node health issues
- BackOff: Retry failures
- Failed: General operation failures
- Killing: Abnormal termination

Provide clear, evidence-based findings with:
- Component: The specific Kubernetes resource affected
- Issue: A clear description of the problem
- Severity: Critical, High, Medium, Low, or Info
- Evidence: Event data supporting the finding
- Recommendation: Specific actions to resolve the issue

Use all available tools to gather comprehensive events data before making your assessment.
Think step-by-step and be thorough in your analysis.
"""
    
    def _tool_get_namespace_events(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Get events for a specific namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            List of events
        """
        namespace = arguments["namespace"]
        return self.k8s_client.get_events(namespace=namespace)
    
    def _tool_get_resource_events(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Get events for a specific resource.
        
        Args:
            arguments: Arguments containing namespace, resource_type, and resource_name
            
        Returns:
            List of events for the resource
        """
        namespace = arguments["namespace"]
        resource_type = arguments["resource_type"]
        resource_name = arguments["resource_name"]
        
        field_selector = f"involvedObject.kind={resource_type},involvedObject.name={resource_name}"
        return self.k8s_client.get_events(namespace=namespace, field_selector=field_selector)
    
    def _tool_get_cluster_events(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Get cluster-wide events.
        
        Args:
            arguments: Arguments containing optional field_selector and limit
            
        Returns:
            List of cluster events
        """
        field_selector = arguments.get("field_selector", "")
        limit = arguments.get("limit", 50)
        
        return self.k8s_client.get_events(limit=limit, field_selector=field_selector)
    
    def _tool_filter_events_by_type(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Filter events by event type.
        
        Args:
            arguments: Arguments containing namespace and event_type
            
        Returns:
            List of filtered events
        """
        namespace = arguments["namespace"]
        event_type = arguments["event_type"]
        
        events = self.k8s_client.get_events(namespace=namespace)
        return [event for event in events if event.get("type") == event_type]
    
    def _tool_filter_events_by_reason(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Filter events by reason.
        
        Args:
            arguments: Arguments containing namespace and reason
            
        Returns:
            List of filtered events
        """
        namespace = arguments["namespace"]
        reason = arguments["reason"]
        
        events = self.k8s_client.get_events(namespace=namespace)
        return [event for event in events if event.get("reason") == reason]