from typing import Dict, List, Any
from agents.mcp_agent import MCPAgent

class MCPTracesAgent(MCPAgent):
    """
    Traces agent using the Model Context Protocol.
    Specializes in analyzing distributed tracing data to identify performance bottlenecks
    and inter-service communication issues.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the traces agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        super().__init__(k8s_client, provider)
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this traces agent.
        
        Returns:
            List of tool definitions
        """
        # Get base tools
        tools = super()._get_agent_tools()
        
        # Add traces-specific tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "get_trace_ids",
                    "description": "Get a list of recent trace IDs",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Filter by service name (optional)",
                                "default": ""
                            },
                            "error_only": {
                                "type": "boolean",
                                "description": "Only return traces with errors",
                                "default": False
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of trace IDs to return",
                                "default": 10
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_trace_details",
                    "description": "Get details for a specific trace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "trace_id": {
                                "type": "string",
                                "description": "The trace ID to retrieve"
                            }
                        },
                        "required": ["trace_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_service_latency_stats",
                    "description": "Get latency statistics for services",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Filter by service name (optional)",
                                "default": ""
                            },
                            "time_range_minutes": {
                                "type": "integer",
                                "description": "Time range in minutes to analyze",
                                "default": 30
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_error_rate_by_service",
                    "description": "Get error rates for services",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "time_range_minutes": {
                                "type": "integer",
                                "description": "Time range in minutes to analyze",
                                "default": 30
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_service_dependencies",
                    "description": "Get service dependency map based on traces",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_name": {
                                "type": "string",
                                "description": "Central service to map dependencies for (optional)",
                                "default": ""
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "find_slow_operations",
                    "description": "Find unusually slow operations across services",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "threshold_ms": {
                                "type": "integer",
                                "description": "Threshold in milliseconds to consider an operation slow",
                                "default": 1000
                            },
                            "time_range_minutes": {
                                "type": "integer",
                                "description": "Time range in minutes to analyze",
                                "default": 30
                            }
                        }
                    }
                }
            }
        ])
        
        return tools
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the traces agent.
        
        Returns:
            String containing the system prompt
        """
        return """You are a Kubernetes Distributed Tracing Expert Agent. Your specialty is analyzing
distributed traces to identify performance bottlenecks, errors, and communication issues between services.

Your responsibilities:
1. Analyze distributed traces to identify performance issues and bottlenecks
2. Detect error patterns and failure points in request flows
3. Identify slow or failing service dependencies
4. Recognize abnormal latency patterns between services
5. Find communication issues and broken links in the service mesh
6. Analyze the critical path in a trace to find optimization opportunities

When analyzing:
- Look for operations with unusually high latency
- Identify services with high error rates
- Find cascading failures where one service failure affects others
- Check for missing spans or broken trace context
- Look for timeout patterns in service-to-service communication
- Identify retry storms or back-pressure issues
- Look for bottleneck services that affect overall request latency
- Check for long database queries or external API calls

Common trace issues to investigate:
- High 95th/99th percentile latency in specific services
- Services with error rates above acceptable thresholds
- Timeout patterns between specific service pairs
- Excessive retries between services
- Database or external dependency bottlenecks
- Serialization issues in parallel operations
- Long queue time before processing

Provide clear, evidence-based findings with:
- Component: The specific service or operation affected
- Issue: A clear description of the problem
- Severity: Critical, High, Medium, Low, or Info
- Evidence: Trace data supporting the finding
- Recommendation: Specific actions to resolve the issue

Use all available tools to gather comprehensive trace data before making your assessment.
Think step-by-step and be thorough in your analysis.
"""
    
    def _tool_get_trace_ids(self, arguments: Dict[str, Any]) -> List[str]:
        """
        Tool implementation: Get a list of recent trace IDs.
        
        Args:
            arguments: Arguments containing optional service_name, error_only, and limit
            
        Returns:
            List of trace IDs
        """
        service_name = arguments.get("service_name", "")
        error_only = arguments.get("error_only", False)
        limit = arguments.get("limit", 10)
        
        return self.k8s_client.get_trace_ids(service_name, error_only, limit)
    
    def _tool_get_trace_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get details for a specific trace.
        
        Args:
            arguments: Arguments containing the trace_id
            
        Returns:
            Dictionary with trace details
        """
        trace_id = arguments["trace_id"]
        return self.k8s_client.get_trace_details(trace_id)
    
    def _tool_get_service_latency_stats(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get latency statistics for services.
        
        Args:
            arguments: Arguments containing optional service_name and time_range_minutes
            
        Returns:
            Dictionary with latency statistics
        """
        service_name = arguments.get("service_name", "")
        time_range_minutes = arguments.get("time_range_minutes", 30)
        
        return self.k8s_client.get_service_latency_stats(service_name, time_range_minutes)
    
    def _tool_get_error_rate_by_service(self, arguments: Dict[str, Any]) -> Dict[str, float]:
        """
        Tool implementation: Get error rates for services.
        
        Args:
            arguments: Arguments containing time_range_minutes
            
        Returns:
            Dictionary mapping service names to error rates
        """
        time_range_minutes = arguments.get("time_range_minutes", 30)
        
        return self.k8s_client.get_error_rate_by_service(time_range_minutes)
    
    def _tool_get_service_dependencies(self, arguments: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Tool implementation: Get service dependency map based on traces.
        
        Args:
            arguments: Arguments containing optional service_name
            
        Returns:
            Dictionary mapping services to their dependencies
        """
        service_name = arguments.get("service_name", "")
        
        return self.k8s_client.get_service_dependencies(service_name)
    
    def _tool_find_slow_operations(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Find unusually slow operations across services.
        
        Args:
            arguments: Arguments containing threshold_ms and time_range_minutes
            
        Returns:
            List of slow operations with their details
        """
        threshold_ms = arguments.get("threshold_ms", 1000)
        time_range_minutes = arguments.get("time_range_minutes", 30)
        
        return self.k8s_client.find_slow_operations(threshold_ms, time_range_minutes)