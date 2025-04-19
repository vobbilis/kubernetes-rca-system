import pandas as pd
from agents.base_agent import BaseAgent

class MetricsAgent(BaseAgent):
    """
    Agent specialized in analyzing Kubernetes metrics data.
    Focuses on resource usage, performance metrics, and anomaly detection.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the metrics agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        super().__init__(k8s_client)
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Analyze metrics data for the specified namespace.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the metrics analysis
        """
        self.reset()
        
        try:
            # Set the context if provided
            if context:
                self.k8s_client.set_context(context)
            
            # Get pod metrics for the namespace
            pod_metrics = self.k8s_client.get_pod_metrics(namespace)
            
            # Get node metrics
            node_metrics = self.k8s_client.get_node_metrics()
            
            # Analyze resource usage
            self._analyze_cpu_usage(pod_metrics)
            self._analyze_memory_usage(pod_metrics)
            self._analyze_node_resources(node_metrics)
            
            # Check for resource limits and requests
            self._analyze_resource_configurations(namespace)
            
            # Analyze HPA (Horizontal Pod Autoscaler) if applicable
            self._analyze_hpa_configurations(namespace)
            
            # Return the analysis results
            return self.get_results()
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during metrics analysis: {str(e)}",
                conclusion="Unable to complete metrics analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _analyze_cpu_usage(self, pod_metrics):
        """
        Analyze CPU usage metrics for pods.
        
        Args:
            pod_metrics: Dictionary of pod metrics data
        """
        if not pod_metrics:
            self.add_reasoning_step(
                observation="No CPU metrics data available",
                conclusion="Unable to analyze CPU usage"
            )
            return
        
        self.add_reasoning_step(
            observation=f"Analyzing CPU usage for {len(pod_metrics)} pods",
            conclusion="Beginning CPU usage analysis"
        )
        
        # Check for high CPU usage
        high_cpu_pods = []
        for pod_name, metrics in pod_metrics.items():
            cpu_usage = metrics.get('cpu', {}).get('usage_percentage', 0)
            
            if cpu_usage > 80:
                high_cpu_pods.append((pod_name, cpu_usage))
                
        if high_cpu_pods:
            pod_list = ", ".join([f"{name} ({usage:.1f}%)" for name, usage in high_cpu_pods])
            self.add_finding(
                component="Pods CPU Usage",
                issue=f"High CPU usage detected in {len(high_cpu_pods)} pods",
                severity="high" if any(usage > 90 for _, usage in high_cpu_pods) else "medium",
                evidence=f"Pods with high CPU usage: {pod_list}",
                recommendation="Consider scaling these deployments or optimizing the application code"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(high_cpu_pods)} pods with CPU usage above 80%",
                conclusion="High CPU usage may indicate resource constraints or inefficient application code"
            )
        else:
            self.add_reasoning_step(
                observation="No pods with high CPU usage detected",
                conclusion="CPU usage appears to be within acceptable limits"
            )
    
    def _analyze_memory_usage(self, pod_metrics):
        """
        Analyze memory usage metrics for pods.
        
        Args:
            pod_metrics: Dictionary of pod metrics data
        """
        if not pod_metrics:
            self.add_reasoning_step(
                observation="No memory metrics data available",
                conclusion="Unable to analyze memory usage"
            )
            return
        
        self.add_reasoning_step(
            observation=f"Analyzing memory usage for {len(pod_metrics)} pods",
            conclusion="Beginning memory usage analysis"
        )
        
        # Check for high memory usage
        high_memory_pods = []
        for pod_name, metrics in pod_metrics.items():
            memory_usage = metrics.get('memory', {}).get('usage_percentage', 0)
            
            if memory_usage > 80:
                high_memory_pods.append((pod_name, memory_usage))
                
        if high_memory_pods:
            pod_list = ", ".join([f"{name} ({usage:.1f}%)" for name, usage in high_memory_pods])
            self.add_finding(
                component="Pods Memory Usage",
                issue=f"High memory usage detected in {len(high_memory_pods)} pods",
                severity="high" if any(usage > 90 for _, usage in high_memory_pods) else "medium",
                evidence=f"Pods with high memory usage: {pod_list}",
                recommendation="Consider increasing memory limits, scaling horizontally, or investigating memory leaks"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(high_memory_pods)} pods with memory usage above 80%",
                conclusion="High memory usage may indicate memory leaks or insufficient resource allocation"
            )
        else:
            self.add_reasoning_step(
                observation="No pods with high memory usage detected",
                conclusion="Memory usage appears to be within acceptable limits"
            )
    
    def _analyze_node_resources(self, node_metrics):
        """
        Analyze resource usage at the node level.
        
        Args:
            node_metrics: Dictionary of node metrics data
        """
        if not node_metrics:
            self.add_reasoning_step(
                observation="No node metrics data available",
                conclusion="Unable to analyze node resource usage"
            )
            return
        
        self.add_reasoning_step(
            observation=f"Analyzing resource usage for {len(node_metrics)} nodes",
            conclusion="Beginning node resource analysis"
        )
        
        # Check for node resource pressure
        pressured_nodes = []
        for node_name, metrics in node_metrics.items():
            cpu_usage = metrics.get('cpu', {}).get('usage_percentage', 0)
            memory_usage = metrics.get('memory', {}).get('usage_percentage', 0)
            
            if cpu_usage > 80 or memory_usage > 80:
                pressured_nodes.append((node_name, cpu_usage, memory_usage))
        
        if pressured_nodes:
            node_list = ", ".join([f"{name} (CPU: {cpu:.1f}%, Memory: {mem:.1f}%)" for name, cpu, mem in pressured_nodes])
            self.add_finding(
                component="Node Resources",
                issue=f"Resource pressure detected on {len(pressured_nodes)} nodes",
                severity="high" if any(cpu > 90 or mem > 90 for _, cpu, mem in pressured_nodes) else "medium",
                evidence=f"Nodes under resource pressure: {node_list}",
                recommendation="Consider adding more nodes to the cluster or optimizing workload distribution"
            )
            
            self.add_reasoning_step(
                observation=f"Detected {len(pressured_nodes)} nodes with high resource usage",
                conclusion="Node resource pressure may be affecting overall cluster performance and pod scheduling"
            )
        else:
            self.add_reasoning_step(
                observation="No nodes with high resource pressure detected",
                conclusion="Node resource usage appears to be within acceptable limits"
            )
    
    def _analyze_resource_configurations(self, namespace):
        """
        Analyze resource requests and limits configurations.
        
        Args:
            namespace: The Kubernetes namespace to analyze
        """
        try:
            # Get deployments in the namespace
            deployments = self.k8s_client.get_deployments(namespace)
            
            if not deployments:
                self.add_reasoning_step(
                    observation=f"No deployments found in namespace {namespace}",
                    conclusion="Unable to analyze resource configurations"
                )
                return
            
            self.add_reasoning_step(
                observation=f"Analyzing resource configurations for {len(deployments)} deployments",
                conclusion="Beginning resource configuration analysis"
            )
            
            # Check for missing resource requests/limits
            missing_resources = []
            
            for deployment in deployments:
                name = deployment['metadata']['name']
                containers = deployment['spec']['template']['spec']['containers']
                
                for container in containers:
                    container_name = container['name']
                    resources = container.get('resources', {})
                    
                    has_cpu_request = 'requests' in resources and 'cpu' in resources['requests']
                    has_memory_request = 'requests' in resources and 'memory' in resources['requests']
                    has_cpu_limit = 'limits' in resources and 'cpu' in resources['limits']
                    has_memory_limit = 'limits' in resources and 'memory' in resources['limits']
                    
                    if not has_cpu_request or not has_memory_request or not has_cpu_limit or not has_memory_limit:
                        missing_resources.append((name, container_name, has_cpu_request, has_memory_request, has_cpu_limit, has_memory_limit))
            
            if missing_resources:
                dep_list = ", ".join([f"{name}/{container}" for name, container, _, _, _, _ in missing_resources])
                self.add_finding(
                    component="Resource Configuration",
                    issue=f"Missing resource requests or limits in {len(missing_resources)} containers",
                    severity="medium",
                    evidence=f"Containers with missing resource configurations: {dep_list}",
                    recommendation="Add appropriate CPU and memory requests and limits to all containers"
                )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(missing_resources)} containers with missing resource configurations",
                    conclusion="Missing resource configurations can lead to resource contention and unpredictable behavior"
                )
            else:
                self.add_reasoning_step(
                    observation="All containers have resource requests and limits configured",
                    conclusion="Resource configurations appear to be properly defined"
                )
                
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error analyzing resource configurations: {str(e)}",
                conclusion="Unable to complete resource configuration analysis"
            )
    
    def _analyze_hpa_configurations(self, namespace):
        """
        Analyze Horizontal Pod Autoscaler configurations.
        
        Args:
            namespace: The Kubernetes namespace to analyze
        """
        try:
            # Get HPAs in the namespace
            hpas = self.k8s_client.get_hpas(namespace)
            
            if not hpas:
                self.add_reasoning_step(
                    observation=f"No HPAs found in namespace {namespace}",
                    conclusion="No autoscaling configurations to analyze"
                )
                return
            
            self.add_reasoning_step(
                observation=f"Analyzing {len(hpas)} Horizontal Pod Autoscalers",
                conclusion="Beginning HPA configuration analysis"
            )
            
            # Check for potentially problematic HPA configurations
            problematic_hpas = []
            
            for hpa in hpas:
                name = hpa['metadata']['name']
                min_replicas = hpa['spec'].get('minReplicas', 1)
                max_replicas = hpa['spec'].get('maxReplicas', 1)
                current_replicas = hpa['status'].get('currentReplicas', 0)
                desired_replicas = hpa['status'].get('desiredReplicas', 0)
                
                # Check if HPA is at max capacity
                if current_replicas == max_replicas and current_replicas > 0:
                    problematic_hpas.append((name, "at_max_capacity", min_replicas, max_replicas, current_replicas))
                
                # Check for narrow scaling range
                if max_replicas - min_replicas < 2 and min_replicas > 1:
                    problematic_hpas.append((name, "narrow_range", min_replicas, max_replicas, current_replicas))
                
                # Check if desired replicas consistently different from current
                if desired_replicas > current_replicas:
                    problematic_hpas.append((name, "scaling_delay", min_replicas, max_replicas, current_replicas))
            
            if problematic_hpas:
                for name, issue_type, min_replicas, max_replicas, current_replicas in problematic_hpas:
                    if issue_type == "at_max_capacity":
                        self.add_finding(
                            component=f"HPA/{name}",
                            issue=f"HPA is at maximum capacity ({current_replicas}/{max_replicas} replicas)",
                            severity="high",
                            evidence=f"HPA {name} is running at maximum capacity of {max_replicas} replicas",
                            recommendation=f"Consider increasing the maximum replicas for this HPA"
                        )
                    elif issue_type == "narrow_range":
                        self.add_finding(
                            component=f"HPA/{name}",
                            issue=f"HPA has a narrow scaling range ({min_replicas}-{max_replicas} replicas)",
                            severity="low",
                            evidence=f"HPA {name} has min={min_replicas}, max={max_replicas} replicas",
                            recommendation=f"Consider widening the scaling range to allow more flexibility"
                        )
                    elif issue_type == "scaling_delay":
                        self.add_finding(
                            component=f"HPA/{name}",
                            issue=f"HPA desired replicas not matching current replicas",
                            severity="medium",
                            evidence=f"HPA {name} has desired replicas > current replicas",
                            recommendation=f"Investigate potential issues preventing scaling or configure less aggressive scaling"
                        )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(problematic_hpas)} HPAs with potential configuration issues",
                    conclusion="HPA configuration issues may be affecting the ability to scale effectively"
                )
            else:
                self.add_reasoning_step(
                    observation="All HPAs appear to be properly configured",
                    conclusion="HPA configurations look appropriate for the current workload"
                )
                
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error analyzing HPA configurations: {str(e)}",
                conclusion="Unable to complete HPA configuration analysis"
            )
