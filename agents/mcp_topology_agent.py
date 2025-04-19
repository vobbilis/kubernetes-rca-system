from typing import Dict, List, Any
from agents.mcp_agent import MCPAgent

class MCPTopologyAgent(MCPAgent):
    """
    Topology agent using the Model Context Protocol.
    Specializes in analyzing Kubernetes resource relationships and connectivity issues.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the topology agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        super().__init__(k8s_client, provider)
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this topology agent.
        
        Returns:
            List of tool definitions
        """
        # Get base tools
        tools = super()._get_agent_tools()
        
        # Add topology-specific tools
        tools.extend([
            {
                "type": "function",
                "function": {
                    "name": "get_namespace_resources",
                    "description": "Get all resources in a namespace",
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
                    "name": "get_service_endpoints",
                    "description": "Get endpoints for a service",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            },
                            "service_name": {
                                "type": "string",
                                "description": "Name of the service"
                            }
                        },
                        "required": ["namespace", "service_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_deployment_details",
                    "description": "Get detailed information about a deployment",
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
                    "name": "get_network_policies",
                    "description": "Get network policies in a namespace",
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
                    "name": "get_service_to_pod_mapping",
                    "description": "Get mapping between services and their backing pods",
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
                    "name": "get_ingress_details",
                    "description": "Get ingress resources and their mappings",
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
        Get the system prompt for the topology agent.
        
        Returns:
            String containing the system prompt
        """
        return """You are a Kubernetes Topology Expert Agent. Your specialty is analyzing the relationships 
between Kubernetes resources, service connectivity, and architectural dependencies.

Your responsibilities:
1. Analyze the service and application topology in the cluster
2. Identify connectivity issues between services
3. Detect misconfigurations in service selectors, labels, and endpoints
4. Find network policy issues that might be blocking communication
5. Analyze service exposure patterns and ingress configurations
6. Identify potential single points of failure

When analyzing:
- Verify that Services have matching pods via selectors
- Check that Endpoints objects have available endpoints
- Look for NetworkPolicies that might be blocking needed traffic
- Check that Ingress resources correctly route to Services
- Verify PersistentVolume claims are bound to volumes
- Check for missing or misconfigured ConfigMaps or Secrets
- Analyze dependencies between microservices
- Identify issues with service-to-service communication

Common topology issues to investigate:
- Services with no endpoints (selector doesn't match any pods)
- NetworkPolicies blocking legitimate traffic
- Ingress rules routing to non-existent services
- Deployments with misconfigured pod templates
- ConfigMaps or Secrets referenced but not existing
- Services exposed on incorrect ports
- Readiness probes failing, causing endpoints to be removed

Provide clear, evidence-based findings with:
- Component: The specific Kubernetes resource affected
- Issue: A clear description of the problem
- Severity: Critical, High, Medium, Low, or Info
- Evidence: Topology data supporting the finding
- Recommendation: Specific actions to resolve the issue

Use all available tools to gather comprehensive topology data before making your assessment.
Think step-by-step and be thorough in your analysis.
"""
    
    def _tool_get_namespace_resources(self, arguments: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Tool implementation: Get all resources in a namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            Dictionary of resource types to lists of resources
        """
        namespace = arguments["namespace"]
        
        pods = self.k8s_client.get_pods(namespace)
        services = self.k8s_client.get_services(namespace)
        deployments = self.k8s_client.get_deployments(namespace)
        statefulsets = self.k8s_client.get_statefulsets(namespace)
        configmaps = self.k8s_client.get_configmaps(namespace)
        secrets = self.k8s_client.get_secrets(namespace)
        
        return {
            "pods": pods,
            "services": services,
            "deployments": deployments,
            "statefulsets": statefulsets,
            "configmaps": configmaps,
            "secrets": [{"name": secret["metadata"]["name"]} for secret in secrets]  # Don't include secret data
        }
    
    def _tool_get_service_endpoints(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get endpoints for a service.
        
        Args:
            arguments: Arguments containing namespace and service_name
            
        Returns:
            Dictionary with service and endpoints information
        """
        namespace = arguments["namespace"]
        service_name = arguments["service_name"]
        
        service = self.k8s_client.get_service(namespace, service_name)
        endpoints = self.k8s_client.get_endpoints(namespace, service_name)
        
        if not service:
            return {"error": f"Service {service_name} not found in namespace {namespace}"}
        
        # Get selector from service
        selector = service.get("spec", {}).get("selector", {})
        
        # Find pods that match the selector
        matching_pods = []
        if selector:
            pods = self.k8s_client.get_pods(namespace)
            for pod in pods:
                pod_labels = pod.get("metadata", {}).get("labels", {})
                if all(pod_labels.get(k) == v for k, v in selector.items()):
                    matching_pods.append(pod)
        
        return {
            "service": service,
            "endpoints": endpoints,
            "selector": selector,
            "matching_pods": [
                {
                    "name": pod.get("metadata", {}).get("name", ""),
                    "ready": self._is_pod_ready(pod),
                    "ip": pod.get("status", {}).get("podIP", "")
                }
                for pod in matching_pods
            ]
        }
    
    def _tool_get_deployment_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get detailed information about a deployment.
        
        Args:
            arguments: Arguments containing namespace and deployment_name
            
        Returns:
            Dictionary with deployment details
        """
        namespace = arguments["namespace"]
        deployment_name = arguments["deployment_name"]
        
        deployment = self.k8s_client.get_deployment(namespace, deployment_name)
        
        if not deployment:
            return {"error": f"Deployment {deployment_name} not found in namespace {namespace}"}
        
        # Get labels used to select pods
        selector = deployment.get("spec", {}).get("selector", {}).get("matchLabels", {})
        
        # Find pods that match the selector
        pods = self.k8s_client.get_pods(namespace)
        matching_pods = []
        for pod in pods:
            pod_labels = pod.get("metadata", {}).get("labels", {})
            if all(pod_labels.get(k) == v for k, v in selector.items()):
                matching_pods.append(pod)
        
        # Check for referenced configmaps and secrets
        configmaps = set()
        secrets = set()
        
        containers = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            # Check env for configmap and secret references
            env = container.get("env", [])
            for env_var in env:
                value_from = env_var.get("valueFrom", {})
                if "configMapKeyRef" in value_from:
                    configmaps.add(value_from["configMapKeyRef"].get("name", ""))
                elif "secretKeyRef" in value_from:
                    secrets.add(value_from["secretKeyRef"].get("name", ""))
            
            # Check envFrom for configmap and secret references
            env_from = container.get("envFrom", [])
            for env_source in env_from:
                if "configMapRef" in env_source:
                    configmaps.add(env_source["configMapRef"].get("name", ""))
                elif "secretRef" in env_source:
                    secrets.add(env_source["secretRef"].get("name", ""))
            
            # Check volumes
            volumes = deployment.get("spec", {}).get("template", {}).get("spec", {}).get("volumes", [])
            for volume in volumes:
                if "configMap" in volume:
                    configmaps.add(volume["configMap"].get("name", ""))
                elif "secret" in volume:
                    secrets.add(volume["secret"].get("name", ""))
        
        return {
            "deployment": deployment,
            "selector": selector,
            "pods": [
                {
                    "name": pod.get("metadata", {}).get("name", ""),
                    "ready": self._is_pod_ready(pod),
                    "status": pod.get("status", {}).get("phase", "")
                }
                for pod in matching_pods
            ],
            "referenced_resources": {
                "configmaps": list(configmaps),
                "secrets": list(secrets)
            }
        }
    
    def _tool_get_network_policies(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get network policies in a namespace.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            Dictionary with network policies and their targets
        """
        namespace = arguments["namespace"]
        
        network_policies = self.k8s_client.get_network_policies(namespace)
        pods = self.k8s_client.get_pods(namespace)
        
        result = {
            "network_policies": [],
            "pod_count": len(pods),
            "potentially_isolated_pods": []
        }
        
        # Keep track of pods that have network policies applied
        pods_with_policies = set()
        
        for policy in network_policies:
            policy_name = policy.get("metadata", {}).get("name", "")
            pod_selector = policy.get("spec", {}).get("podSelector", {})
            
            # Find pods affected by this policy
            affected_pods = []
            match_labels = pod_selector.get("matchLabels", {})
            
            for pod in pods:
                pod_name = pod.get("metadata", {}).get("name", "")
                pod_labels = pod.get("metadata", {}).get("labels", {})
                
                # Check if pod matches the policy selector
                if all(pod_labels.get(k) == v for k, v in match_labels.items()):
                    affected_pods.append(pod_name)
                    pods_with_policies.add(pod_name)
            
            ingress_rules = policy.get("spec", {}).get("ingress", [])
            egress_rules = policy.get("spec", {}).get("egress", [])
            
            policy_details = {
                "name": policy_name,
                "pod_selector": pod_selector,
                "affected_pods": affected_pods,
                "ingress_rules_count": len(ingress_rules),
                "egress_rules_count": len(egress_rules),
                "policy_types": policy.get("spec", {}).get("policyTypes", [])
            }
            
            result["network_policies"].append(policy_details)
        
        # Find pods that don't have any network policies
        for pod in pods:
            pod_name = pod.get("metadata", {}).get("name", "")
            if pod_name not in pods_with_policies:
                result["potentially_isolated_pods"].append(pod_name)
        
        return result
    
    def _tool_get_service_to_pod_mapping(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get mapping between services and their backing pods.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            Dictionary mapping services to their backing pods
        """
        namespace = arguments["namespace"]
        
        services = self.k8s_client.get_services(namespace)
        pods = self.k8s_client.get_pods(namespace)
        
        mapping = {}
        
        for service in services:
            service_name = service.get("metadata", {}).get("name", "")
            selector = service.get("spec", {}).get("selector", {})
            
            matching_pods = []
            unready_pods = []
            
            # Skip headless services
            if not selector:
                mapping[service_name] = {
                    "service_type": service.get("spec", {}).get("type", ""),
                    "selector": "None (headless)",
                    "ports": service.get("spec", {}).get("ports", []),
                    "matching_pods": [],
                    "unready_pods": [],
                    "has_endpoints": False
                }
                continue
            
            # Find pods that match the selector
            for pod in pods:
                pod_name = pod.get("metadata", {}).get("name", "")
                pod_labels = pod.get("metadata", {}).get("labels", {})
                
                # Check if pod matches the service selector
                if all(pod_labels.get(k) == v for k, v in selector.items()):
                    pod_info = {
                        "name": pod_name,
                        "ip": pod.get("status", {}).get("podIP", ""),
                        "status": pod.get("status", {}).get("phase", "")
                    }
                    
                    if self._is_pod_ready(pod):
                        matching_pods.append(pod_info)
                    else:
                        unready_pods.append(pod_info)
            
            # Get endpoints to check if service has endpoints
            endpoints = self.k8s_client.get_endpoints(namespace, service_name)
            has_endpoints = False
            
            if endpoints and "subsets" in endpoints:
                for subset in endpoints.get("subsets", []):
                    if subset.get("addresses", []):
                        has_endpoints = True
                        break
            
            mapping[service_name] = {
                "service_type": service.get("spec", {}).get("type", ""),
                "selector": selector,
                "ports": service.get("spec", {}).get("ports", []),
                "matching_pods": matching_pods,
                "unready_pods": unready_pods,
                "has_endpoints": has_endpoints
            }
        
        return {"services": mapping}
    
    def _tool_get_ingress_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tool implementation: Get ingress resources and their mappings.
        
        Args:
            arguments: Arguments containing the namespace
            
        Returns:
            Dictionary with ingress details and validations
        """
        namespace = arguments["namespace"]
        
        ingresses = self.k8s_client.get_ingresses(namespace)
        services = self.k8s_client.get_services(namespace)
        
        service_names = [service.get("metadata", {}).get("name", "") for service in services]
        
        result = {
            "ingresses": [],
            "issues": []
        }
        
        for ingress in ingresses:
            ingress_name = ingress.get("metadata", {}).get("name", "")
            ingress_details = {
                "name": ingress_name,
                "rules": [],
                "tls": ingress.get("spec", {}).get("tls", [])
            }
            
            # Process rules
            for rule in ingress.get("spec", {}).get("rules", []):
                host = rule.get("host", "*")
                paths = []
                
                for path in rule.get("http", {}).get("paths", []):
                    service_name = path.get("backend", {}).get("service", {}).get("name", "")
                    service_port = path.get("backend", {}).get("service", {}).get("port", {}).get("number", "")
                    path_pattern = path.get("path", "/")
                    
                    paths.append({
                        "path": path_pattern,
                        "service": service_name,
                        "port": service_port
                    })
                    
                    # Check if the service exists
                    if service_name and service_name not in service_names:
                        result["issues"].append({
                            "ingress": ingress_name,
                            "issue": f"Ingress references non-existent service '{service_name}'",
                            "host": host,
                            "path": path_pattern
                        })
                
                ingress_details["rules"].append({
                    "host": host,
                    "paths": paths
                })
            
            result["ingresses"].append(ingress_details)
        
        return result
    
    def _is_pod_ready(self, pod: Dict[str, Any]) -> bool:
        """
        Check if a pod is ready.
        
        Args:
            pod: Pod data
            
        Returns:
            True if the pod is ready, False otherwise
        """
        if pod.get("status", {}).get("phase", "") != "Running":
            return False
        
        conditions = pod.get("status", {}).get("conditions", [])
        for condition in conditions:
            if condition.get("type") == "Ready":
                return condition.get("status") == "True"
        
        return False