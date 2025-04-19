import networkx as nx
from agents.base_agent import BaseAgent

class TopologyAgent(BaseAgent):
    """
    Agent specialized in analyzing Kubernetes topology.
    Focuses on service dependencies, network flows, and architectural issues.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the topology agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        super().__init__(k8s_client)
        self.service_graph = nx.DiGraph()
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Analyze topology for the specified namespace.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the topology analysis
        """
        self.reset()
        self.service_graph = nx.DiGraph()
        
        try:
            # Set the context if provided
            if context:
                self.k8s_client.set_context(context)
            
            # Get all resources in the namespace
            deployments = self.k8s_client.get_deployments(namespace)
            services = self.k8s_client.get_services(namespace)
            pods = self.k8s_client.get_pods(namespace)
            ingresses = self.k8s_client.get_ingresses(namespace)
            configmaps = self.k8s_client.get_configmaps(namespace)
            secrets = self.k8s_client.get_secrets(namespace)
            
            # Get network policies
            network_policies = self.k8s_client.get_network_policies(namespace)
            
            self.add_reasoning_step(
                observation=f"Collected resource data from namespace {namespace}",
                conclusion="Beginning topology analysis"
            )
            
            # Build service dependency graph
            self._build_service_graph(deployments, services, pods, ingresses, configmaps, secrets)
            
            # Analyze the service graph for issues
            if self.service_graph.number_of_nodes() > 0:
                self._analyze_service_dependencies()
                self._analyze_single_points_of_failure()
                self._analyze_isolated_services()
            
            # Analyze network policies
            self._analyze_network_policies(network_policies, services)
            
            # Analyze ingress configurations
            self._analyze_ingress_configurations(ingresses, services)
            
            # Analyze resource dependencies
            self._analyze_resource_dependencies(deployments, configmaps, secrets)
            
            # Prepare topology data for visualization
            topology_data = self._prepare_topology_data()
            
            # Add topology data to results
            results = self.get_results()
            results['topology_data'] = topology_data
            
            return results
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during topology analysis: {str(e)}",
                conclusion="Unable to complete topology analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _build_service_graph(self, deployments, services, pods, ingresses, configmaps, secrets):
        """
        Build a graph representing service dependencies.
        
        Args:
            deployments: List of deployments
            services: List of services
            pods: List of pods
            ingresses: List of ingresses
            configmaps: List of config maps
            secrets: List of secrets
        """
        # Add nodes for each service and deployment
        for service in services:
            service_name = service['metadata']['name']
            self.service_graph.add_node(
                service_name, 
                type='service',
                ports=service.get('spec', {}).get('ports', []),
                selector=service.get('spec', {}).get('selector', {})
            )
        
        for deployment in deployments:
            deployment_name = deployment['metadata']['name']
            self.service_graph.add_node(
                deployment_name, 
                type='deployment',
                replicas=deployment.get('spec', {}).get('replicas', 1),
                labels=deployment.get('metadata', {}).get('labels', {}),
                containers=len(deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers', []))
            )
            
            # Connect deployments to services based on labels/selectors
            for service in services:
                service_name = service['metadata']['name']
                service_selector = service.get('spec', {}).get('selector', {})
                deployment_labels = deployment.get('metadata', {}).get('labels', {})
                
                # Check if this deployment matches the service's selector
                if all(item in deployment_labels.items() for item in service_selector.items()):
                    self.service_graph.add_edge(service_name, deployment_name, type='selects')
        
        # Add ingress nodes and connections
        for ingress in ingresses:
            ingress_name = ingress['metadata']['name']
            self.service_graph.add_node(ingress_name, type='ingress')
            
            # Connect ingress to services
            rules = ingress.get('spec', {}).get('rules', [])
            for rule in rules:
                if 'http' in rule:
                    for path in rule.get('http', {}).get('paths', []):
                        backend_service = path.get('backend', {}).get('serviceName', None)
                        if backend_service and backend_service in self.service_graph:
                            self.service_graph.add_edge(ingress_name, backend_service, type='routes')
        
        # Add ConfigMap and Secret dependencies
        self._add_config_dependencies(deployments, configmaps, secrets)
        
        # Try to infer additional service dependencies from environment variables
        self._infer_dependencies_from_env(deployments, services)
        
        self.add_reasoning_step(
            observation=f"Built service graph with {self.service_graph.number_of_nodes()} nodes and {self.service_graph.number_of_edges()} edges",
            conclusion="Service topology mapping complete"
        )
    
    def _add_config_dependencies(self, deployments, configmaps, secrets):
        """
        Add ConfigMap and Secret nodes and their connections to deployments.
        
        Args:
            deployments: List of deployments
            configmaps: List of config maps
            secrets: List of secrets
        """
        # Add ConfigMap nodes
        for configmap in configmaps:
            cm_name = configmap['metadata']['name']
            self.service_graph.add_node(cm_name, type='configmap')
        
        # Add Secret nodes
        for secret in secrets:
            secret_name = secret['metadata']['name']
            self.service_graph.add_node(secret_name, type='secret')
        
        # Connect deployments to their ConfigMaps and Secrets
        for deployment in deployments:
            deployment_name = deployment['metadata']['name']
            containers = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            volumes = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('volumes', [])
            
            # Check volume mounts for ConfigMap and Secret references
            for volume in volumes:
                if 'configMap' in volume:
                    cm_name = volume['configMap']['name']
                    if cm_name in self.service_graph:
                        self.service_graph.add_edge(deployment_name, cm_name, type='mounts')
                
                if 'secret' in volume:
                    secret_name = volume['secret']['secretName']
                    if secret_name in self.service_graph:
                        self.service_graph.add_edge(deployment_name, secret_name, type='mounts')
            
            # Check environment variables for ConfigMap and Secret references
            for container in containers:
                env_from = container.get('envFrom', [])
                env = container.get('env', [])
                
                for env_source in env_from:
                    if 'configMapRef' in env_source:
                        cm_name = env_source['configMapRef']['name']
                        if cm_name in self.service_graph:
                            self.service_graph.add_edge(deployment_name, cm_name, type='env_from')
                    
                    if 'secretRef' in env_source:
                        secret_name = env_source['secretRef']['name']
                        if secret_name in self.service_graph:
                            self.service_graph.add_edge(deployment_name, secret_name, type='env_from')
                
                for env_var in env:
                    if 'valueFrom' in env_var:
                        value_from = env_var['valueFrom']
                        
                        if 'configMapKeyRef' in value_from:
                            cm_name = value_from['configMapKeyRef']['name']
                            if cm_name in self.service_graph:
                                self.service_graph.add_edge(deployment_name, cm_name, type='env_var')
                        
                        if 'secretKeyRef' in value_from:
                            secret_name = value_from['secretKeyRef']['name']
                            if secret_name in self.service_graph:
                                self.service_graph.add_edge(deployment_name, secret_name, type='env_var')
    
    def _infer_dependencies_from_env(self, deployments, services):
        """
        Infer service dependencies from environment variables.
        
        Args:
            deployments: List of deployments
            services: List of services
        """
        # Create a map of service names to their cluster DNS names
        service_dns_map = {}
        for service in services:
            service_name = service['metadata']['name']
            service_dns_map[service_name] = service_name
            service_dns_map[f"{service_name}.{service['metadata']['namespace']}"] = service_name
            service_dns_map[f"{service_name}.{service['metadata']['namespace']}.svc"] = service_name
            service_dns_map[f"{service_name}.{service['metadata']['namespace']}.svc.cluster.local"] = service_name
        
        # Check environment variables for service references
        for deployment in deployments:
            deployment_name = deployment['metadata']['name']
            containers = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            
            for container in containers:
                env = container.get('env', [])
                
                for env_var in env:
                    value = env_var.get('value', '')
                    
                    # Check if any service DNS name appears in env var values
                    for dns_name, service_name in service_dns_map.items():
                        if dns_name in value and service_name in self.service_graph:
                            # This deployment likely depends on this service
                            self.service_graph.add_edge(deployment_name, service_name, type='depends_on')
    
    def _analyze_service_dependencies(self):
        """
        Analyze the service dependency graph for issues.
        """
        # Check for service dependency cycles
        try:
            cycles = list(nx.simple_cycles(self.service_graph))
            if cycles:
                cycle_str = ' → '.join(cycles[0] + [cycles[0][0]])
                self.add_finding(
                    component="Service Architecture",
                    issue="Circular dependency detected in service architecture",
                    severity="medium",
                    evidence=f"Dependency cycle: {cycle_str}",
                    recommendation="Refactor the service architecture to eliminate circular dependencies"
                )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(cycles)} circular dependencies in the service graph",
                    conclusion="Circular dependencies can lead to deployment and scaling issues"
                )
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error detecting cycles: {str(e)}",
                conclusion="Unable to analyze circular dependencies"
            )
        
        # Check for deep dependency chains
        # Find the longest path in the graph
        longest_path = None
        longest_length = 0
        
        for node in self.service_graph.nodes():
            for target in self.service_graph.nodes():
                if node != target:
                    try:
                        paths = list(nx.all_simple_paths(self.service_graph, node, target))
                        if paths:
                            path_length = len(max(paths, key=len))
                            if path_length > longest_length:
                                longest_length = path_length
                                longest_path = max(paths, key=len)
                    except nx.NetworkXNoPath:
                        continue
        
        if longest_path and len(longest_path) >= 4:  # Consider chains of 4+ services as potentially problematic
            path_str = ' → '.join(longest_path)
            self.add_finding(
                component="Service Architecture",
                issue="Long dependency chain detected",
                severity="low",
                evidence=f"Long dependency path: {path_str}",
                recommendation="Consider simplifying the architecture or implementing caching to reduce dependency chain impacts"
            )
            
            self.add_reasoning_step(
                observation=f"Detected a dependency chain of length {len(longest_path)}: {path_str}",
                conclusion="Long dependency chains can increase latency and reduce reliability"
            )
    
    def _analyze_single_points_of_failure(self):
        """
        Analyze the service graph for single points of failure.
        """
        # Calculate node centrality to find critical services
        try:
            # Use betweenness centrality to find nodes that many paths go through
            betweenness = nx.betweenness_centrality(self.service_graph)
            
            # Find nodes with high centrality (potential single points of failure)
            critical_nodes = [node for node, value in betweenness.items() if value > 0.5]
            
            for node in critical_nodes:
                node_type = self.service_graph.nodes[node].get('type', 'unknown')
                if node_type in ['deployment', 'service']:
                    replica_count = self.service_graph.nodes[node].get('replicas', 1) if node_type == 'deployment' else 1
                    
                    if replica_count < 2:
                        self.add_finding(
                            component=f"{node_type.capitalize()}/{node}",
                            issue="Potential single point of failure with high centrality",
                            severity="high",
                            evidence=f"This {node_type} is a central component with only {replica_count} replica",
                            recommendation=f"Increase the number of replicas and consider implementing redundancy"
                        )
                        
                        self.add_reasoning_step(
                            observation=f"Detected {node} as a central component with low redundancy",
                            conclusion="This component could be a single point of failure"
                        )
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error analyzing single points of failure: {str(e)}",
                conclusion="Unable to identify potential single points of failure"
            )
    
    def _analyze_isolated_services(self):
        """
        Analyze the service graph for isolated services.
        """
        # Find isolated nodes
        isolated_nodes = list(nx.isolates(self.service_graph))
        
        service_nodes = [node for node in isolated_nodes 
                        if self.service_graph.nodes[node].get('type') == 'service']
        
        deployment_nodes = [node for node in isolated_nodes 
                           if self.service_graph.nodes[node].get('type') == 'deployment']
        
        # Report isolated services
        if service_nodes:
            service_list = ", ".join(service_nodes)
            self.add_finding(
                component="Service Architecture",
                issue=f"Found {len(service_nodes)} isolated services",
                severity="low",
                evidence=f"Services without connections: {service_list}",
                recommendation="Verify if these services are still needed or if they should be connected to other components"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(service_nodes)} services with no connections",
                conclusion="These services may be unused or misconfigured"
            )
        
        # Report isolated deployments
        if deployment_nodes:
            deployment_list = ", ".join(deployment_nodes)
            self.add_finding(
                component="Service Architecture",
                issue=f"Found {len(deployment_nodes)} isolated deployments",
                severity="medium",
                evidence=f"Deployments without connections: {deployment_list}",
                recommendation="Verify if these deployments are still needed or if they should be exposed via services"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(deployment_nodes)} deployments with no connections",
                conclusion="These deployments may be unused or missing service selectors"
            )
    
    def _analyze_network_policies(self, network_policies, services):
        """
        Analyze network policies for potential issues.
        
        Args:
            network_policies: List of network policies
            services: List of services
        """
        if not network_policies:
            self.add_reasoning_step(
                observation="No network policies found in the namespace",
                conclusion="No network security restrictions are in place"
            )
            
            # Check if there are multiple services - if so, suggest network policies
            if len(services) > 1:
                self.add_finding(
                    component="Network Security",
                    issue="No network policies defined in a multi-service namespace",
                    severity="medium",
                    evidence=f"Found {len(services)} services but no network policies",
                    recommendation="Implement network policies to restrict communication between services"
                )
            
            return
        
        self.add_reasoning_step(
            observation=f"Found {len(network_policies)} network policies",
            conclusion="Analyzing network policy configurations"
        )
        
        # Check if network policies are too permissive
        permissive_policies = []
        for policy in network_policies:
            policy_name = policy['metadata']['name']
            
            # Look for overly permissive ingress rules
            ingress_rules = policy.get('spec', {}).get('ingress', [])
            for rule in ingress_rules:
                # An empty rule allows all ingress
                if not rule:
                    permissive_policies.append((policy_name, 'ingress', 'empty rule'))
                    continue
                
                # Check for rules that allow from all sources
                if 'from' not in rule or not rule['from']:
                    permissive_policies.append((policy_name, 'ingress', 'no from selector'))
        
        # Report permissive policies
        if permissive_policies:
            policies_str = ", ".join([f"{name} ({kind}: {issue})" for name, kind, issue in permissive_policies])
            self.add_finding(
                component="Network Policies",
                issue="Overly permissive network policies detected",
                severity="medium",
                evidence=f"Permissive policies: {policies_str}",
                recommendation="Restrict network policies to allow only necessary communication"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(permissive_policies)} overly permissive network policies",
                conclusion="These policies may allow unnecessary network access"
            )
        
        # Check for services without network policies
        services_with_policies = set()
        for policy in network_policies:
            pod_selector = policy.get('spec', {}).get('podSelector', {})
            match_labels = pod_selector.get('matchLabels', {})
            
            # Find services that match this policy's pod selector
            for service in services:
                service_name = service['metadata']['name']
                service_selector = service.get('spec', {}).get('selector', {})
                
                # If all policy match labels are in the service selector, the policy applies to this service
                if all(item in service_selector.items() for item in match_labels.items()):
                    services_with_policies.add(service_name)
        
        # Find services without policies
        all_service_names = {service['metadata']['name'] for service in services}
        services_without_policies = all_service_names - services_with_policies
        
        if services_without_policies:
            services_str = ", ".join(services_without_policies)
            self.add_finding(
                component="Network Policies",
                issue=f"Found {len(services_without_policies)} services without network policies",
                severity="medium",
                evidence=f"Services without network policies: {services_str}",
                recommendation="Implement network policies for all services to secure communication"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(services_without_policies)} services without network policies",
                conclusion="These services may accept traffic from any source"
            )
    
    def _analyze_ingress_configurations(self, ingresses, services):
        """
        Analyze ingress configurations for potential issues.
        
        Args:
            ingresses: List of ingresses
            services: List of services
        """
        if not ingresses:
            # Check if any services might need external access
            external_service_candidates = []
            for service in services:
                service_name = service['metadata']['name']
                service_type = service.get('spec', {}).get('type', 'ClusterIP')
                
                # If a service is of type ClusterIP but has 'api', 'web', 'ui', or 'frontend' in its name,
                # it might need an ingress
                if service_type == 'ClusterIP' and any(keyword in service_name.lower() for keyword in ['api', 'web', 'ui', 'frontend']):
                    external_service_candidates.append(service_name)
            
            if external_service_candidates:
                services_str = ", ".join(external_service_candidates)
                self.add_finding(
                    component="External Access",
                    issue="Potential external services without Ingress resources",
                    severity="low",
                    evidence=f"Services that might need external access: {services_str}",
                    recommendation="Consider creating Ingress resources for services that require external access"
                )
            
            return
        
        self.add_reasoning_step(
            observation=f"Found {len(ingresses)} ingress resources",
            conclusion="Analyzing ingress configurations"
        )
        
        # Check for ingresses without TLS
        ingresses_without_tls = []
        for ingress in ingresses:
            ingress_name = ingress['metadata']['name']
            tls_config = ingress.get('spec', {}).get('tls', [])
            
            if not tls_config:
                ingresses_without_tls.append(ingress_name)
        
        if ingresses_without_tls:
            ingresses_str = ", ".join(ingresses_without_tls)
            self.add_finding(
                component="Ingress Security",
                issue=f"Found {len(ingresses_without_tls)} ingresses without TLS configuration",
                severity="high",
                evidence=f"Ingresses without TLS: {ingresses_str}",
                recommendation="Configure TLS for all ingress resources to ensure encrypted communication"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(ingresses_without_tls)} ingresses without TLS",
                conclusion="These ingresses are exposing services over unencrypted HTTP"
            )
        
        # Check for ingresses pointing to non-existent services
        broken_ingresses = []
        service_names = {service['metadata']['name'] for service in services}
        
        for ingress in ingresses:
            ingress_name = ingress['metadata']['name']
            rules = ingress.get('spec', {}).get('rules', [])
            
            for rule in rules:
                if 'http' in rule:
                    for path in rule.get('http', {}).get('paths', []):
                        backend_service = path.get('backend', {}).get('serviceName', None)
                        if backend_service and backend_service not in service_names:
                            broken_ingresses.append((ingress_name, backend_service))
        
        if broken_ingresses:
            ingresses_str = ", ".join([f"{ingress} → {service}" for ingress, service in broken_ingresses])
            self.add_finding(
                component="Ingress Configuration",
                issue=f"Found {len(broken_ingresses)} ingress rules pointing to non-existent services",
                severity="high",
                evidence=f"Broken ingress rules: {ingresses_str}",
                recommendation="Update or remove ingress rules pointing to non-existent services"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(broken_ingresses)} ingress rules with invalid service references",
                conclusion="These ingress rules will not work as expected"
            )
    
    def _analyze_resource_dependencies(self, deployments, configmaps, secrets):
        """
        Analyze resource dependencies for potential issues.
        
        Args:
            deployments: List of deployments
            configmaps: List of config maps
            secrets: List of secrets
        """
        configmap_names = {cm['metadata']['name'] for cm in configmaps}
        secret_names = {secret['metadata']['name'] for secret in secrets}
        
        # Check for deployments referencing non-existent ConfigMaps or Secrets
        missing_references = []
        
        for deployment in deployments:
            deployment_name = deployment['metadata']['name']
            containers = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
            volumes = deployment.get('spec', {}).get('template', {}).get('spec', {}).get('volumes', [])
            
            # Check volume mounts
            for volume in volumes:
                if 'configMap' in volume and volume['configMap']['name'] not in configmap_names:
                    missing_references.append((deployment_name, 'ConfigMap', volume['configMap']['name']))
                
                if 'secret' in volume and volume['secret']['secretName'] not in secret_names:
                    missing_references.append((deployment_name, 'Secret', volume['secret']['secretName']))
            
            # Check environment variables
            for container in containers:
                env_from = container.get('envFrom', [])
                env = container.get('env', [])
                
                for env_source in env_from:
                    if 'configMapRef' in env_source and env_source['configMapRef']['name'] not in configmap_names:
                        missing_references.append((deployment_name, 'ConfigMap', env_source['configMapRef']['name']))
                    
                    if 'secretRef' in env_source and env_source['secretRef']['name'] not in secret_names:
                        missing_references.append((deployment_name, 'Secret', env_source['secretRef']['name']))
                
                for env_var in env:
                    if 'valueFrom' in env_var:
                        value_from = env_var['valueFrom']
                        
                        if 'configMapKeyRef' in value_from and value_from['configMapKeyRef']['name'] not in configmap_names:
                            missing_references.append((deployment_name, 'ConfigMap', value_from['configMapKeyRef']['name']))
                        
                        if 'secretKeyRef' in value_from and value_from['secretKeyRef']['name'] not in secret_names:
                            missing_references.append((deployment_name, 'Secret', value_from['secretKeyRef']['name']))
        
        if missing_references:
            references_str = ", ".join([f"{dep} → {kind}/{name}" for dep, kind, name in missing_references])
            self.add_finding(
                component="Resource Dependencies",
                issue=f"Found {len(missing_references)} references to non-existent resources",
                severity="high",
                evidence=f"Missing references: {references_str}",
                recommendation="Create the missing ConfigMaps and Secrets, or update the deployments to reference existing resources"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(missing_references)} references to non-existent ConfigMaps or Secrets",
                conclusion="These missing dependencies will prevent pods from starting correctly"
            )
    
    def _prepare_topology_data(self):
        """
        Prepare topology data for visualization.
        
        Returns:
            dict: Topology data in a format suitable for visualization
        """
        nodes = []
        edges = []
        
        # Convert nodes to the desired format
        for node_name in self.service_graph.nodes():
            node_data = self.service_graph.nodes[node_name]
            node_type = node_data.get('type', 'unknown')
            
            nodes.append({
                'id': node_name,
                'label': node_name,
                'type': node_type,
                'data': node_data
            })
        
        # Convert edges to the desired format
        for source, target, data in self.service_graph.edges(data=True):
            edge_type = data.get('type', 'unknown')
            
            edges.append({
                'source': source,
                'target': target,
                'label': edge_type,
                'type': edge_type
            })
        
        return {
            'nodes': nodes,
            'edges': edges
        }
