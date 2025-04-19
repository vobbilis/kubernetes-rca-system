from typing import Dict, List, Any
from agents.mcp_agent import MCPAgent

class MCPMetricsAgent(MCPAgent):
    """
    Metrics agent using the Model Context Protocol.
    Specializes in analyzing Kubernetes metrics data to identify resource-related issues.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the metrics agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        super().__init__(k8s_client, provider)
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this metrics agent.
        
        Returns:
            List of tool definitions
        """
        # Get base tools
        tools = super()._get_agent_tools()
        
        # Add metrics-specific tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "get_pod_metrics",
                    "description": "Get metrics data for pods in the specified namespace",
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
                    "name": "get_node_metrics",
                    "description": "Get metrics data for all nodes in the cluster",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_deployment_resource_usage",
                    "description": "Get resource usage for a specific deployment",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "deployment_name": {
                                "type": "string",
                                "description": "Name of the deployment"
                            }
                        },
                        "required": ["namespace", "deployment_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_resource_quotas",
                    "description": "Get resource quotas for a namespace",
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
                    "name": "get_hpa_status",
                    "description": "Get HorizontalPodAutoscaler status for a namespace",
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
            }
        ])
        
        return tools
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for the metrics agent.
        
        Returns:
            String containing the system prompt
        """
        return """You are a Kubernetes Metrics Expert Agent. Your specialty is analyzing resource utilization, 
performance metrics, and identifying resource-related issues in Kubernetes clusters.

Your responsibilities:
1. Analyze CPU, memory, and other resource usage patterns
2. Identify resource constraints, bottlenecks, and inefficiencies
3. Detect underutilized or overutilized resources
4. Evaluate the effectiveness of resource limits and requests
5. Analyze Horizontal Pod Autoscaler (HPA) configurations and behavior
6. Look for patterns and anomalies in resource usage over time

When analyzing:
- Compare actual usage against allocated resources
- Identify pods/containers with consistently high resource usage (>80%)
- Check for resource quota issues or limit ranges
- Evaluate if CPU throttling is occurring
- Look for memory pressure or OOMKilled events
- Check if HPA is scaling appropriately

Provide clear, evidence-based findings with:
- Component: The specific Kubernetes resource affected
- Issue: A clear description of the problem
- Severity: Critical, High, Medium, Low, or Info
- Evidence: Metrics data supporting the finding
- Recommendation: Specific actions to resolve the issue

Use all available tools to gather comprehensive metrics data before making your assessment.
Think step-by-step and be thorough in your analysis.
"""
    
    def _tool_get_pod_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get metrics for pods in a namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            Dictionary of pod metrics
        """
        namespace = arguments["namespace"]
        return self.k8s_client.get_pod_metrics(namespace)
    
    def _tool_get_node_metrics(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get metrics for all nodes.
        
        Args:
            arguments: Empty arguments dictionary
            
        Returns:
            Dictionary of node metrics
        """
        return self.k8s_client.get_node_metrics()
    
    def _tool_get_deployment_resource_usage(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get resource usage for a specific deployment.
        
        Args:
            arguments: Arguments containing namespace and deployment_name
            
        Returns:
            Dictionary of deployment resource usage
        """
        namespace = arguments["namespace"]
        deployment_name = arguments["deployment_name"]
        
        # Get the deployment
        deployment = self.k8s_client.get_deployment(namespace, deployment_name)
        
        # Get pods for this deployment
        pod_metrics = self.k8s_client.get_pod_metrics(namespace)
        
        # Filter pods by deployment
        deployment_pods = {}
        for pod_name, metrics in pod_metrics.items():
            if deployment_name in pod_name:
                deployment_pods[pod_name] = metrics
        
        return {
            "deployment": deployment,
            "pod_metrics": deployment_pods
        }
    
    def _tool_get_resource_quotas(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Get resource quotas for a namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            List of resource quotas
        """
        namespace = arguments["namespace"]
        return self.k8s_client.get_resource_quotas(namespace)
    
    def _tool_get_hpa_status(self, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Tool implementation: Get HPA status for a namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            List of HPAs with status
        """
        namespace = arguments["namespace"]
        return self.k8s_client.get_hpas(namespace)