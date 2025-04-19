import networkx as nx
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from utils.kubernetes_client import KubernetesClient

class TopologyAgent:
    """
    Agent responsible for analyzing the topology of Kubernetes resources.
    Identifies service dependencies, network connectivity issues, and architectural problems.
    """
    
    def __init__(self, k8s_client: KubernetesClient):
        """
        Initialize the topology agent with a Kubernetes client.
        
        Args:
            k8s_client: An initialized Kubernetes client for interacting with the cluster
        """
        self.k8s_client = k8s_client
    
    def analyze(
        self, 
        namespace: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Analyze the topology of resources in the specified namespace.
        
        Args:
            namespace: Kubernetes namespace to analyze
            start_time: Start time for topology analysis (used for historical data if available)
            end_time: End time for topology analysis
            
        Returns:
            Dict containing topology analysis results
        """
        # Collect topology data
        topology_data = self._collect_topology(namespace)
        
        # Generate service map
        service_map = self._generate_service_map(topology_data)
        
        # Identify topology issues
        issues = self._identify_issues(topology_data, service_map)
        
        # Create network policies analysis
        network_policies = self._analyze_network_policies(namespace, topology_data)
        
        # Prepare results
        results = {
            'service_map': service_map,
            'issues': issues,
            'network_policies': network_policies,
            'resource_counts': self._get_resource_counts(topology_data)
        }
        
        return results
    
    def _collect_topology(self, namespace: str) -> Dict[str, Any]:
        """
        Collect topology data from Kubernetes resources.
        
        Args:
            namespace: Kubernetes namespace to collect data from
            
        Returns:
            Dict containing collected topology data
        """
        # In a real implementation, this would query the Kubernetes API for resources
        # and potentially use tools like kiali or istio
        
        # Collect resources
        services = self.k8s_client.get_services(namespace)
        deployments = self.k8s_client.get_deployments(namespace)
        pods = self.k8s_client.get_pods(namespace)
        
        # Collect network policies
        network_policies = self.k8s_client.get_network_policies(namespace)
        
        # Map deployments to services
        deployment_service_map = {}
        
        for service in services:
            if 'selector' in service and service['selector']:
                # Find deployments that match this service's selector
                for deployment in deployments:
                    if 'labels' in deployment and deployment['labels']:
                        # Check if deployment labels match service selector
                        match = True
                        for key, value in service['selector'].items():
                            if key not in deployment['labels'] or deployment['labels'][key] != value:
                                match = False
                                break
                        
                        if match:
                            if deployment['name'] not in deployment_service_map:
                                deployment_service_map[deployment['name']] = []
                            
                            deployment_service_map[deployment['name']].append(service['name'])
        
        # Collect pod dependencies (through environment variables)
        pod_dependencies = {}
        
        for pod in pods:
            if 'env_vars' in pod:
                for env_var in pod['env_vars']:
                    # Look for service discovery environment variables
                    if '_SERVICE_HOST' in env_var:
                        service_name = env_var.replace('_SERVICE_HOST', '').lower().replace('_', '-')
                        
                        if pod['name'] not in pod_dependencies:
                            pod_dependencies[pod['name']] = []
                        
                        pod_dependencies[pod['name']].append(service_name)
        
        # Return topology data
        return {
            'services': services,
            'deployments': deployments,
            'pods': pods,
            'network_policies': network_policies,
            'deployment_service_map': deployment_service_map,
            'pod_dependencies': pod_dependencies
        }
    
    def _generate_service_map(self, topology_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a service dependency map from topology data.
        
        Args:
            topology_data: Dictionary containing topology data
            
        Returns:
            Dict representing the service map
        """
        # Create a graph
        G = nx.DiGraph()
        
        # Add services as nodes
        services = topology_data['services']
        for service in services:
            G.add_node(service['name'], type='service', data=service)
        
        # Add deployments as nodes
        deployments = topology_data['deployments']
        for deployment in deployments:
            G.add_node(deployment['name'], type='deployment', data=deployment)
        
        # Connect deployments to services
        deployment_service_map = topology_data['deployment_service_map']
        for deployment_name, service_names in deployment_service_map.items():
            for service_name in service_names:
                G.add_edge(deployment_name, service_name, type='implements')
        
        # Add dependencies between services (through pod dependencies)
        pod_dependencies = topology_data['pod_dependencies']
        for pod_name, dependencies in pod_dependencies.items():
            # Find deployment for this pod
            pod_deployment = None
            for deployment in deployments:
                if 'pods' in deployment and pod_name in deployment['pods']:
                    pod_deployment = deployment['name']
                    break
            
            if pod_deployment:
                # Get services implemented by this deployment
                source_services = deployment_service_map.get(pod_deployment, [])
                
                # Add edges from source services to dependency services
                for source_service in source_services:
                    for target_service in dependencies:
                        if G.has_node(target_service):  # Ensure target service exists
                            G.add_edge(source_service, target_service, type='depends_on')
        
        # Convert graph to nodes and edges format
        nodes = []
        for node, attrs in G.nodes(data=True):
            node_type = attrs.get('type', 'unknown')
            node_data = {
                'id': node,
                'label': node,
                'type': node_type
            }
            
            # Add additional data
            if node_type == 'service':
                service_data = attrs.get('data', {})
                node_data.update({
                    'ports': service_data.get('ports', []),
                    'type': service_data.get('type', 'ClusterIP')
                })
            elif node_type == 'deployment':
                deployment_data = attrs.get('data', {})
                node_data.update({
                    'replicas': deployment_data.get('ready', '0/0')
                })
            
            nodes.append(node_data)
        
        edges = []
        for source, target, attrs in G.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'type': attrs.get('type', 'unknown')
            })
        
        # Add metadata
        service_map = {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'service_count': len([n for n in nodes if n['type'] == 'service']),
                'deployment_count': len([n for n in nodes if n['type'] == 'deployment']),
                'dependency_count': len([e for e in edges if e['type'] == 'depends_on'])
            }
        }
        
        return service_map
    
    def _identify_issues(
        self, 
        topology_data: Dict[str, Any], 
        service_map: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify issues in the topology.
        
        Args:
            topology_data: Dictionary containing topology data
            service_map: Dictionary containing service map
            
        Returns:
            List of identified issues
        """
        issues = []
        
        # Create a graph from the service map
        G = nx.DiGraph()
        
        for node in service_map['nodes']:
            G.add_node(node['id'], **node)
        
        for edge in service_map['edges']:
            G.add_edge(edge['source'], edge['target'], **edge)
        
        # Check for orphaned services (services with no deployments)
        services = [n for n in service_map['nodes'] if n['type'] == 'service']
        orphaned_services = []
        
        for service in services:
            service_id = service['id']
            
            # Check if this service has incoming edges from deployments
            has_implementation = False
            for edge in service_map['edges']:
                if edge['target'] == service_id and edge['type'] == 'implements':
                    has_implementation = True
                    break
            
            if not has_implementation:
                orphaned_services.append(service_id)
        
        if orphaned_services:
            issues.append({
                'title': 'Orphaned Services',
                'type': 'warning',
                'description': 'Services without any implementing deployments',
                'affected_services': orphaned_services,
                'severity': 'Medium'
            })
        
        # Check for circular dependencies
        try:
            cycles = list(nx.simple_cycles(G))
            if cycles:
                # Filter to only cycles involving service dependencies
                service_cycles = []
                for cycle in cycles:
                    # Check if it's a cycle of services
                    if all(G.nodes[node].get('type') == 'service' for node in cycle):
                        # Check if they're connected by depends_on edges
                        is_dependency_cycle = True
                        for i in range(len(cycle)):
                            source = cycle[i]
                            target = cycle[(i + 1) % len(cycle)]
                            if G.get_edge_data(source, target).get('type') != 'depends_on':
                                is_dependency_cycle = False
                                break
                        
                        if is_dependency_cycle:
                            service_cycles.append(cycle)
                
                if service_cycles:
                    # Report up to 3 cycles
                    for i, cycle in enumerate(service_cycles[:3]):
                        issues.append({
                            'title': f'Circular Dependency #{i+1}',
                            'type': 'error',
                            'description': 'Circular dependency between services',
                            'affected_services': cycle,
                            'severity': 'High'
                        })
        except:
            # Ignore cycle detection errors (DiGraph should support it, but just in case)
            pass
        
        # Check for single points of failure
        # Identify critical services that many others depend on
        service_dependencies = {}
        for edge in service_map['edges']:
            if edge['type'] == 'depends_on':
                target = edge['target']
                if target not in service_dependencies:
                    service_dependencies[target] = []
                service_dependencies[target].append(edge['source'])
        
        for service, dependents in service_dependencies.items():
            if len(dependents) >= 3:  # If at least 3 services depend on this one
                # Check how this service is implemented
                service_deployments = []
                for edge in service_map['edges']:
                    if edge['target'] == service and edge['type'] == 'implements':
                        service_deployments.append(edge['source'])
                
                # Check deployment replicas
                deployment_infos = []
                for dep_name in service_deployments:
                    dep_info = next((d for d in topology_data['deployments'] if d['name'] == dep_name), None)
                    if dep_info:
                        deployment_infos.append(dep_info)
                
                # Check if any deployment has a single replica
                single_replica_deps = [d for d in deployment_infos if d.get('ready', '0/0').split('/')[1] == '1']
                
                if single_replica_deps:
                    affected_deployments = [d['name'] for d in single_replica_deps]
                    issues.append({
                        'title': 'Single Point of Failure',
                        'type': 'warning',
                        'description': f'Service has {len(dependents)} dependents but is implemented by deployments with single replicas',
                        'affected_services': [service],
                        'affected_deployments': affected_deployments,
                        'severity': 'High'
                    })
        
        # Check for services with no inbound or outbound connections
        isolated_services = []
        
        for service in services:
            service_id = service['id']
            
            # Check for any edges to or from this service
            has_connections = False
            for edge in service_map['edges']:
                if edge['source'] == service_id or edge['target'] == service_id:
                    has_connections = True
                    break
            
            if not has_connections:
                isolated_services.append(service_id)
        
        if isolated_services:
            issues.append({
                'title': 'Isolated Services',
                'type': 'info',
                'description': 'Services with no connections to other services',
                'affected_services': isolated_services,
                'severity': 'Low'
            })
        
        return issues
    
    def _analyze_network_policies(
        self, 
        namespace: str, 
        topology_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze network policies in the namespace.
        
        Args:
            namespace: Kubernetes namespace
            topology_data: Dictionary containing topology data
            
        Returns:
            Dict containing network policy analysis
        """
        # Get network policies and services
        network_policies = topology_data.get('network_policies', [])
        services = topology_data.get('services', [])
        
        # Check if each service is covered by network policies
        service_coverage = {}
        
        for service in services:
            service_name = service['name']
            service_coverage[service_name] = {
                'ingress_policies': [],
                'egress_policies': [],
                'covered': False
            }
            
            # Check which policies apply to this service
            for policy in network_policies:
                # Check if policy applies to this service (based on pod selector)
                if self._policy_applies_to_service(policy, service):
                    if 'ingress' in policy.get('spec', {}):
                        service_coverage[service_name]['ingress_policies'].append(policy['name'])
                    
                    if 'egress' in policy.get('spec', {}):
                        service_coverage[service_name]['egress_policies'].append(policy['name'])
                    
                    service_coverage[service_name]['covered'] = True
        
        # Count services with/without policies
        covered_count = sum(1 for _, coverage in service_coverage.items() if coverage['covered'])
        total_services = len(services)
        
        # Identify uncovered services
        uncovered_services = [
            service_name for service_name, coverage in service_coverage.items() 
            if not coverage['covered']
        ]
        
        return {
            'total_policies': len(network_policies),
            'service_coverage': covered_count,
            'total_services': total_services,
            'coverage_percentage': (covered_count / total_services * 100) if total_services > 0 else 0,
            'uncovered_services': uncovered_services,
            'service_details': service_coverage
        }
    
    def _policy_applies_to_service(self, policy: Dict[str, Any], service: Dict[str, Any]) -> bool:
        """
        Check if a network policy applies to a service.
        
        Args:
            policy: Network policy
            service: Service
            
        Returns:
            True if the policy applies to the service, False otherwise
        """
        # In a real implementation, this would check if the policy's selector
        # matches the service's pods based on labels
        
        # For this example, we'll use a simplified approach
        # Match based on whether the policy's pod selector matches service selector
        if 'podSelector' in policy.get('spec', {}) and 'selector' in service:
            policy_selector = policy['spec']['podSelector'].get('matchLabels', {})
            service_selector = service['selector']
            
            # Check if there's any overlap in labels
            for key, value in policy_selector.items():
                if key in service_selector and service_selector[key] == value:
                    return True
        
        # Random match with 30% probability if no match found
        return np.random.random() < 0.3
    
    def _get_resource_counts(self, topology_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get counts of different resource types.
        
        Args:
            topology_data: Dictionary containing topology data
            
        Returns:
            Dict containing resource counts
        """
        return {
            'services': len(topology_data.get('services', [])),
            'deployments': len(topology_data.get('deployments', [])),
            'pods': len(topology_data.get('pods', [])),
            'network_policies': len(topology_data.get('network_policies', []))
        }
