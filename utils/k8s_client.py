import subprocess
import json
import yaml
import re
import os
from datetime import datetime
from kubernetes import client, config

class K8sClient:
    """
    Client for interacting with Kubernetes API and obtaining cluster information.
    Provides methods to query Kubernetes resources and execute kubectl commands.
    """
    
    def __init__(self):
        """Initialize the Kubernetes client."""
        self.connected = False
        self.current_context = None
        self.available_contexts = []
        self.last_connection_error = None  # Store the last connection error for debugging
        self.server_url = None  # Store the server URL for reference
        
        # Disable SSL verification globally for the client
        # This is necessary for working with self-signed certs like those from ngrok
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Try to load the Kubernetes configuration
        self._load_config()
        
    def _load_config(self):
        """Load the Kubernetes configuration from the default location."""
        try:
            # Try using our custom safe-kubeconfig.yaml first
            custom_kubeconfig = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                           "kube-config", "safe-kubeconfig.yaml")
            
            if os.path.exists(custom_kubeconfig):
                print(f"Loading Kubernetes configuration from {custom_kubeconfig}")
                
                # First, directly parse the kubeconfig file to get the server URL
                try:
                    with open(custom_kubeconfig, 'r') as f:
                        kube_config = yaml.safe_load(f)
                        server_url = None
                        
                        # Extract server URL directly from the kubeconfig file
                        for cluster in kube_config.get('clusters', []):
                            if cluster.get('cluster') and 'server' in cluster['cluster']:
                                server_url = cluster['cluster']['server']
                                print(f"Found server URL in kubeconfig: {server_url}")
                                break
                        
                        if not server_url:
                            print("ERROR: No server URL found in kubeconfig!")
                            return
                except Exception as yaml_error:
                    print(f"Error parsing kubeconfig file: {yaml_error}")
                    return
                
                # Create a configuration with SSL verification disabled
                api_config = client.Configuration()
                api_config.host = server_url  # Set the server URL directly
                api_config.verify_ssl = False
                api_config.debug = True
                
                # Set defaults for client certificates
                api_config.cert_file = None
                api_config.key_file = None
                api_config.ssl_ca_cert = None
                
                # Load user credentials from kubeconfig
                try:
                    # Get the current context
                    current_context = kube_config.get('current-context')
                    
                    # Find the user associated with this context
                    context_info = None
                    for ctx in kube_config.get('contexts', []):
                        if ctx.get('name') == current_context:
                            context_info = ctx
                            break
                    
                    if context_info:
                        user_name = context_info.get('context', {}).get('user')
                        
                        # Find the user credentials
                        for user in kube_config.get('users', []):
                            if user.get('name') == user_name and 'user' in user:
                                user_data = user['user']
                                
                                # Check if we have client certificate data
                                if 'client-certificate-data' in user_data:
                                    # Save the client cert to a temp file
                                    cert_data = user_data['client-certificate-data']
                                    
                                # Check if we have client key data
                                if 'client-key-data' in user_data:
                                    # Save the client key to a temp file
                                    key_data = user_data['client-key-data']
                                    
                                # Use token auth if available
                                if 'token' in user_data:
                                    api_config.api_key['authorization'] = f"Bearer {user_data['token']}"
                                    
                                break
                except Exception as auth_error:
                    print(f"Error setting up authentication: {auth_error}")
                
                # Create API client with this configuration
                api_client = client.ApiClient(api_config)
                
                # Store context information
                if 'current-context' in kube_config:
                    current_context = kube_config.get('current-context')
                    self.available_contexts = [current_context]
                    self.current_context = current_context
                else:
                    # Default if no current context is set
                    self.available_contexts = ["default"]
                    self.current_context = "default"
                self.connected = True
                
                # Initialize API clients
                self.core_v1 = client.CoreV1Api(api_client)
                self.apps_v1 = client.AppsV1Api(api_client)
                self.networking_v1 = client.NetworkingV1Api(api_client)
                self.custom_objects_api = client.CustomObjectsApi(api_client)
                
                # Test the connection
                try:
                    print(f"DEBUG: Attempting to connect to Kubernetes API at {api_config.host}")
                    # Enable detailed HTTP debugging
                    import http.client as http_client
                    http_client.HTTPConnection.debuglevel = 1
                    
                    # Test the API connection
                    namespaces = self.core_v1.list_namespace(limit=1)
                    print(f"Successfully validated Kubernetes API connection. Found namespaces: {[ns.metadata.name for ns in namespaces.items]}")
                    http_client.HTTPConnection.debuglevel = 0
                except Exception as api_error:
                    error_msg = f"Failed to validate Kubernetes API connection: {api_error}"
                    print(error_msg)
                    print(f"DEBUG: API Host was: {api_config.host}")
                    print(f"DEBUG: SSL Verification was: {api_config.verify_ssl}")
                    self.connected = False
                    self.last_connection_error = error_msg
                    self.server_url = api_config.host
            else:
                # If custom config doesn't exist, try in-cluster config
                try:
                    print("Custom config not found, trying in-cluster configuration")
                    config.load_incluster_config()
                    self.connected = True
                    self.current_context = "in-cluster"
                    self.available_contexts = ["in-cluster"]
                    
                    # Initialize API clients
                    self.core_v1 = client.CoreV1Api()
                    self.apps_v1 = client.AppsV1Api()
                    self.networking_v1 = client.NetworkingV1Api()
                    self.custom_objects_api = client.CustomObjectsApi()
                except config.config_exception.ConfigException:
                    print("Not running in a cluster and no kubeconfig found")
                    self.connected = False
        except Exception as e:
            print(f"Failed to load Kubernetes configuration: {e}")
            self.connected = False
            
    def is_connected(self):
        """
        Check if the client is connected to a Kubernetes cluster.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.connected
        
    def reload_config(self):
        """
        Reload the Kubernetes configuration.
        This is useful after updating the kubeconfig file.
        
        Returns:
            bool: True if the reload was successful, False otherwise
        """
        try:
            # Reset connection state
            self.connected = False
            self.current_context = None
            self.available_contexts = []
            self.last_connection_error = None
            self.server_url = None
            
            # Reload configuration
            self._load_config()
            
            return self.connected
        except Exception as e:
            print(f"Failed to reload Kubernetes configuration: {e}")
            return False
        
    def get_connection_error(self):
        """
        Get the last connection error message.
        
        Returns:
            str: Last connection error message or None if no error
        """
        return self.last_connection_error
    
    def get_available_contexts(self):
        """
        Get a list of available Kubernetes contexts.
        
        Returns:
            list: Available Kubernetes contexts
        """
        return self.available_contexts
    
    def get_current_context(self):
        """
        Get the current Kubernetes context.
        
        Returns:
            str: Current context name
        """
        return self.current_context
    
    def set_context(self, context_name):
        """
        Set the Kubernetes context.
        
        Args:
            context_name: Name of the context to set
            
        Returns:
            bool: True if context was set successfully, False otherwise
        """
        if context_name not in self.available_contexts:
            return False
        
        try:
            # Get the kubeconfig path
            custom_kubeconfig = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                         "kube-config", "safe-kubeconfig.yaml")
            
            if not os.path.exists(custom_kubeconfig):
                print(f"Kubeconfig file not found: {custom_kubeconfig}")
                return False
                
            # First, directly parse the kubeconfig file to get the server URL
            with open(custom_kubeconfig, 'r') as f:
                kube_config = yaml.safe_load(f)
                server_url = None
                
                # Extract server URL directly from the kubeconfig file
                for cluster in kube_config.get('clusters', []):
                    if cluster.get('cluster') and 'server' in cluster['cluster']:
                        server_url = cluster['cluster']['server']
                        print(f"Found server URL in kubeconfig: {server_url}")
                        break
                
                if not server_url:
                    print("ERROR: No server URL found in kubeconfig!")
                    return False
            
            # Create a configuration with SSL verification disabled
            api_config = client.Configuration()
            api_config.host = server_url  # Set the server URL directly
            api_config.verify_ssl = False
            api_config.debug = True
            
            # Set defaults for client certificates
            api_config.cert_file = None
            api_config.key_file = None
            api_config.ssl_ca_cert = None
            
            # Get the current context
            if 'current-context' in kube_config:
                current_context = kube_config.get('current-context')
                self.current_context = current_context
            else:
                # Default to the context name that was requested
                self.current_context = context_name
            
            # Create API client with this configuration
            api_client = client.ApiClient(api_config)
            
            # Reinitialize API clients with SSL verification disabled
            self.core_v1 = client.CoreV1Api(api_client)
            self.apps_v1 = client.AppsV1Api(api_client)
            self.networking_v1 = client.NetworkingV1Api(api_client)
            self.custom_objects_api = client.CustomObjectsApi(api_client)
            
            # Test the connection
            try:
                print(f"DEBUG: Testing connection to Kubernetes API at {api_config.host}")
                # Enable detailed HTTP debugging
                import http.client as http_client
                http_client.HTTPConnection.debuglevel = 1
                
                # Test the API connection
                namespaces = self.core_v1.list_namespace(limit=1)
                print(f"Successfully validated Kubernetes API connection. Found namespaces: {[ns.metadata.name for ns in namespaces.items]}")
                http_client.HTTPConnection.debuglevel = 0
                self.connected = True
            except Exception as api_error:
                print(f"Failed to validate Kubernetes API connection: {api_error}")
                print(f"DEBUG: API Host was: {api_config.host}")
                print(f"DEBUG: SSL Verification was: {api_config.verify_ssl}")
                self.connected = False
            
            return self.connected
        except Exception as e:
            print(f"Failed to set context to {context_name}: {e}")
            return False
    
    def get_namespaces(self):
        """
        Get a list of all namespaces in the cluster.
        
        Returns:
            list: Namespace names
        """
        if not self.connected:
            return []
        
        try:
            namespaces = self.core_v1.list_namespace()
            return [ns.metadata.name for ns in namespaces.items]
        except Exception as e:
            print(f"Failed to get namespaces: {e}")
            return []
    
    def get_pods(self, namespace):
        """
        Get all pods in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Pod data
        """
        if not self.connected:
            return []
        
        try:
            pods = self.core_v1.list_namespaced_pod(namespace)
            return [self._convert_k8s_obj_to_dict(pod) for pod in pods.items]
        except Exception as e:
            print(f"Failed to get pods in namespace {namespace}: {e}")
            return []
    
    def get_pod(self, namespace, pod_name):
        """
        Get detailed information for a specific pod.
        
        Args:
            namespace: Namespace of the pod
            pod_name: Name of the pod
            
        Returns:
            dict: Pod data or None if not found
        """
        if not self.connected:
            return None
        
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            return self._convert_k8s_obj_to_dict(pod)
        except Exception as e:
            print(f"Failed to get pod {pod_name} in namespace {namespace}: {e}")
            return None
            
    def get_pod_status(self, namespace, pod_name):
        """
        Get detailed status information for a specific pod.
        
        Args:
            namespace: Namespace of the pod
            pod_name: Name of the pod
            
        Returns:
            dict: Pod status data or None if not found
        """
        if not self.connected:
            return None
        
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            return self._convert_k8s_obj_to_dict(pod)
        except Exception as e:
            print(f"Failed to get status for pod {pod_name} in namespace {namespace}: {e}")
            return None
    
    def get_services(self, namespace):
        """
        Get all services in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Service data
        """
        if not self.connected:
            return []
        
        try:
            services = self.core_v1.list_namespaced_service(namespace)
            return [self._convert_k8s_obj_to_dict(svc) for svc in services.items]
        except Exception as e:
            print(f"Failed to get services in namespace {namespace}: {e}")
            return []
    
    def get_deployments(self, namespace):
        """
        Get all deployments in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Deployment data
        """
        if not self.connected:
            return []
        
        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace)
            return [self._convert_k8s_obj_to_dict(deploy) for deploy in deployments.items]
        except Exception as e:
            print(f"Failed to get deployments in namespace {namespace}: {e}")
            return []
    
    def get_node_metrics(self):
        """
        Get metrics for all nodes in the cluster.
        Uses kubectl to get metrics-server data.
        
        Returns:
            dict: Node metrics data
        """
        if not self.connected:
            return {}
        
        try:
            # Try using the metrics API
            result = self._run_kubectl_command(["top", "nodes", "--no-headers"])
            
            if result['success']:
                metrics = {}
                for line in result['output'].splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        node_name = parts[0]
                        cpu_usage = self._parse_percentage(parts[2])
                        memory_usage = self._parse_percentage(parts[4])
                        
                        metrics[node_name] = {
                            'cpu': {
                                'usage_percentage': cpu_usage
                            },
                            'memory': {
                                'usage_percentage': memory_usage
                            }
                        }
                
                return metrics
            else:
                print(f"Failed to get node metrics: {result['error']}")
                return {}
        except Exception as e:
            print(f"Failed to get node metrics: {e}")
            return {}
    
    def get_pod_metrics(self, namespace):
        """
        Get metrics for all pods in a namespace.
        Uses kubectl to get metrics-server data.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            dict: Pod metrics data
        """
        if not self.connected:
            return {}
        
        try:
            # Try using the metrics API
            result = self._run_kubectl_command(["top", "pods", "--no-headers", "-n", namespace])
            
            if result['success']:
                metrics = {}
                for line in result['output'].splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        pod_name = parts[0]
                        cpu_usage = self._parse_cpu_value(parts[1])
                        memory_usage = self._parse_memory_value(parts[2])
                        
                        metrics[pod_name] = {
                            'cpu': {
                                'usage': cpu_usage,
                                'usage_percentage': 0  # Will be calculated if limits are available
                            },
                            'memory': {
                                'usage': memory_usage,
                                'usage_percentage': 0  # Will be calculated if limits are available
                            }
                        }
                
                # Get resource limits for pods and calculate usage percentages
                pods = self.get_pods(namespace)
                for pod in pods:
                    pod_name = pod['metadata']['name']
                    if pod_name in metrics:
                        containers = pod['spec']['containers']
                        total_cpu_limit = 0
                        total_memory_limit = 0
                        
                        for container in containers:
                            resources = container.get('resources', {})
                            limits = resources.get('limits', {})
                            
                            if 'cpu' in limits:
                                cpu_limit = self._parse_cpu_value(limits['cpu'])
                                total_cpu_limit += cpu_limit
                            
                            if 'memory' in limits:
                                memory_limit = self._parse_memory_value(limits['memory'])
                                total_memory_limit += memory_limit
                        
                        # Calculate usage percentages
                        if total_cpu_limit > 0:
                            metrics[pod_name]['cpu']['usage_percentage'] = (metrics[pod_name]['cpu']['usage'] / total_cpu_limit) * 100
                        
                        if total_memory_limit > 0:
                            metrics[pod_name]['memory']['usage_percentage'] = (metrics[pod_name]['memory']['usage'] / total_memory_limit) * 100
                
                return metrics
            else:
                print(f"Failed to get pod metrics: {result['error']}")
                return {}
        except Exception as e:
            print(f"Failed to get pod metrics: {e}")
            return {}
    
    def get_pod_logs(self, namespace, pod_name, container_name=None, tail_lines=100):
        """
        Get logs for a pod.
        
        Args:
            namespace: Namespace of the pod
            pod_name: Name of the pod
            container_name: Name of the container (optional)
            tail_lines: Number of lines to return from the end of the logs
            
        Returns:
            str: Pod logs
        """
        if not self.connected:
            return ""
        
        try:
            if container_name:
                return self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container_name,
                    tail_lines=tail_lines
                )
            else:
                return self.core_v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    tail_lines=tail_lines
                )
        except Exception as e:
            print(f"Failed to get logs for pod {pod_name}: {e}")
            return ""
    
    def get_events(self, namespace, field_selector=None):
        """
        Get events for a namespace.
        
        Args:
            namespace: Namespace to query
            field_selector: Optional field selector to filter events
            
        Returns:
            list: Event data
        """
        if not self.connected:
            return []
        
        try:
            # Default field selector to show only non-normal events if none provided
            if field_selector is None:
                field_selector = "type!=Normal"
                
            events = self.core_v1.list_namespaced_event(namespace, field_selector=field_selector)
            return [self._convert_k8s_obj_to_dict(event) for event in events.items]
        except Exception as e:
            print(f"Failed to get events for namespace {namespace}: {e}")
            return []
    
    def get_ingresses(self, namespace):
        """
        Get all ingresses in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Ingress data
        """
        if not self.connected:
            return []
        
        try:
            ingresses = self.networking_v1.list_namespaced_ingress(namespace)
            return [self._convert_k8s_obj_to_dict(ingress) for ingress in ingresses.items]
        except Exception as e:
            print(f"Failed to get ingresses in namespace {namespace}: {e}")
            return []
    
    def get_network_policies(self, namespace):
        """
        Get all network policies in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: NetworkPolicy data
        """
        if not self.connected:
            return []
        
        try:
            network_policies = self.networking_v1.list_namespaced_network_policy(namespace)
            return [self._convert_k8s_obj_to_dict(policy) for policy in network_policies.items]
        except Exception as e:
            print(f"Failed to get network policies in namespace {namespace}: {e}")
            return []
    
    def get_configmaps(self, namespace):
        """
        Get all ConfigMaps in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: ConfigMap data
        """
        if not self.connected:
            return []
        
        try:
            configmaps = self.core_v1.list_namespaced_config_map(namespace)
            return [self._convert_k8s_obj_to_dict(cm) for cm in configmaps.items]
        except Exception as e:
            print(f"Failed to get ConfigMaps in namespace {namespace}: {e}")
            return []
    
    def get_secrets(self, namespace):
        """
        Get all Secrets in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Secret data (without the actual secret values)
        """
        if not self.connected:
            return []
        
        try:
            secrets = self.core_v1.list_namespaced_secret(namespace)
            secret_list = []
            
            for secret in secrets.items:
                # Convert to dict but remove the data to avoid exposing sensitive information
                secret_dict = self._convert_k8s_obj_to_dict(secret)
                if 'data' in secret_dict:
                    # Replace actual values with placeholder
                    secret_dict['data'] = {k: '**REDACTED**' for k in secret_dict['data'].keys()}
                secret_list.append(secret_dict)
            
            return secret_list
        except Exception as e:
            print(f"Failed to get Secrets in namespace {namespace}: {e}")
            return []
    
    def get_hpas(self, namespace):
        """
        Get all Horizontal Pod Autoscalers in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: HPA data
        """
        if not self.connected:
            return []
        
        try:
            result = self._run_kubectl_command(["get", "hpa", "-n", namespace, "-o", "json"])
            
            if result['success']:
                hpa_list = json.loads(result['output'])
                return hpa_list.get('items', [])
            else:
                print(f"Failed to get HPAs: {result['error']}")
                return []
        except Exception as e:
            print(f"Failed to get HPAs: {e}")
            return []
    
    def get_recently_terminated_pods(self, namespace, max_age_minutes=60):
        """
        Get recently terminated pods.
        
        Args:
            namespace: Namespace to query
            max_age_minutes: Maximum age of terminated pods to return (in minutes)
            
        Returns:
            list: Terminated pod data
        """
        # This would ideally query terminated pods directly, but the API doesn't provide
        # a straightforward way to do this. In a real implementation, you might store
        # this information in a database or use a more sophisticated approach.
        # For now, we'll return an empty list.
        return []
    
    def get_services_by_label(self, label_selector):
        """
        Get services across all namespaces matching a label selector.
        
        Args:
            label_selector: Label selector (e.g., "app=nginx")
            
        Returns:
            list: Service data
        """
        if not self.connected:
            return []
        
        try:
            services = self.core_v1.list_service_for_all_namespaces(label_selector=label_selector)
            return [self._convert_k8s_obj_to_dict(svc) for svc in services.items]
        except Exception as e:
            print(f"Failed to get services with label {label_selector}: {e}")
            return []
    
    def get_nodes(self):
        """
        Get all nodes in the cluster.
        
        Returns:
            list: Node data
        """
        if not self.connected:
            return []
        
        try:
            nodes = self.core_v1.list_node()
            return [self._convert_k8s_obj_to_dict(node) for node in nodes.items]
        except Exception as e:
            print(f"Failed to get nodes: {e}")
            return []
    
    def get_current_time(self):
        """
        Get the current time in ISO format.
        
        Returns:
            str: Current time in ISO format
        """
        return datetime.now().isoformat()
    
    def are_traces_available(self):
        """
        Check if distributed tracing is available in the cluster.
        
        Returns:
            bool: True if tracing is available, False otherwise
        """
        # Check for common tracing backends like Jaeger, Zipkin, or OpenTelemetry Collector
        if not self.connected:
            return False
            
        try:
            # Look for tracing services in the cluster
            all_namespaces = self.get_namespaces()
            for namespace in all_namespaces:
                services = self.get_services(namespace)
                
                for service in services:
                    name = service['metadata']['name'].lower()
                    # Check for common tracing service names
                    if any(tracer in name for tracer in ['jaeger', 'zipkin', 'opentelemetry', 'tempo', 'trace']):
                        return True
                        
            # If no tracing services found, check for tracing custom resources
            try:
                # Check for OpenTelemetry resources
                otel_resources = self._run_kubectl_command(["get", "opentelemetrycollector", "--all-namespaces"])
                if otel_resources['success'] and len(otel_resources['output'].strip()) > 0:
                    return True
            except Exception:
                pass
                
            return False
        except Exception as e:
            print(f"Error checking for traces availability: {e}")
            return False
    
    def _run_kubectl_command(self, args):
        """
        Run a kubectl command and return the result.
        
        Args:
            args: Command arguments (excluding 'kubectl')
            
        Returns:
            dict: Command result with keys 'success', 'output', and 'error'
        """
        cmd = ["kubectl"] + args
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return {
                'success': True,
                'output': result.stdout,
                'error': None
            }
        except subprocess.CalledProcessError as e:
            return {
                'success': False,
                'output': None,
                'error': e.stderr
            }
    
    def _convert_k8s_obj_to_dict(self, k8s_obj):
        """
        Convert Kubernetes object to a dictionary.
        
        Args:
            k8s_obj: Kubernetes object
            
        Returns:
            dict: Dictionary representation of the object
        """
        # Convert to a JSON-compatible format
        json_data = client.ApiClient().sanitize_for_serialization(k8s_obj)
        return json_data
    
    def _parse_percentage(self, percentage_str):
        """
        Parse a percentage string to a float.
        
        Args:
            percentage_str: Percentage string (e.g., '45%')
            
        Returns:
            float: Percentage value
        """
        try:
            return float(percentage_str.strip('%'))
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_cpu_value(self, cpu_str):
        """
        Parse a CPU value string to a float (in cores).
        
        Args:
            cpu_str: CPU string (e.g., '100m', '0.1')
            
        Returns:
            float: CPU value in cores
        """
        try:
            cpu_str = str(cpu_str).strip()
            if cpu_str.endswith('m'):
                return float(cpu_str[:-1]) / 1000.0
            else:
                return float(cpu_str)
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_memory_value(self, memory_str):
        """
        Parse a memory value string to a float (in bytes).
        
        Args:
            memory_str: Memory string (e.g., '100Mi', '1Gi')
            
        Returns:
            float: Memory value in bytes
        """
        try:
            memory_str = str(memory_str).strip()
            
            # Define unit multipliers
            units = {
                'Ki': 1024,
                'Mi': 1024 ** 2,
                'Gi': 1024 ** 3,
                'Ti': 1024 ** 4,
                'Pi': 1024 ** 5,
                'K': 1000,
                'M': 1000 ** 2,
                'G': 1000 ** 3,
                'T': 1000 ** 4,
                'P': 1000 ** 5,
                'E': 1000 ** 6,
                'Ei': 1024 ** 6
            }
            
            # Match value and unit
            match = re.match(r'^(\d+(?:\.\d+)?)([KMGTPE]i?)?(.*)$', memory_str)
            if match:
                value = float(match.group(1))
                unit = match.group(2) or ''
                
                if unit in units:
                    return value * units[unit]
                else:
                    return value
            else:
                return float(memory_str)
        except (ValueError, AttributeError):
            return 0.0
            
    def get_resource_details(self, resource_type, resource_name, namespace):
        """
        Get detailed information about a specific Kubernetes resource.
        
        Args:
            resource_type: Type of resource (pod, deployment, service, etc.)
            resource_name: Name of the resource
            namespace: Namespace where the resource is located
            
        Returns:
            dict: Resource details
        """
        if not self.connected:
            return {"error": "Not connected to Kubernetes API"}
        
        try:
            if resource_type.lower() == 'pod':
                resource = self.core_v1.read_namespaced_pod(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'deployment':
                resource = self.apps_v1.read_namespaced_deployment(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'service':
                resource = self.core_v1.read_namespaced_service(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'configmap':
                resource = self.core_v1.read_namespaced_config_map(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'secret':
                resource = self.core_v1.read_namespaced_secret(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'persistentvolumeclaim' or resource_type.lower() == 'pvc':
                resource = self.core_v1.read_namespaced_persistent_volume_claim(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'statefulset':
                resource = self.apps_v1.read_namespaced_stateful_set(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'daemonset':
                resource = self.apps_v1.read_namespaced_daemon_set(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'job':
                resource = self.batch_v1.read_namespaced_job(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'cronjob':
                resource = self.batch_v1.read_namespaced_cron_job(name=resource_name, namespace=namespace)
            elif resource_type.lower() == 'ingress':
                resource = self.networking_v1.read_namespaced_ingress(name=resource_name, namespace=namespace)
            else:
                return {"error": f"Unsupported resource type: {resource_type}"}
                
            # Convert the resource to a dictionary
            resource_dict = self._convert_k8s_obj_to_dict(resource)
            
            # Add human-readable timestamps
            if 'metadata' in resource_dict and 'creationTimestamp' in resource_dict['metadata']:
                timestamp = resource_dict['metadata']['creationTimestamp']
                if timestamp:
                    created_time = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
                    now = datetime.utcnow()
                    diff = now - created_time
                    
                    days = diff.days
                    hours, remainder = divmod(diff.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    if days > 0:
                        resource_dict['metadata']['createdAgo'] = f"{days}d {hours}h ago"
                    elif hours > 0:
                        resource_dict['metadata']['createdAgo'] = f"{hours}h {minutes}m ago"
                    else:
                        resource_dict['metadata']['createdAgo'] = f"{minutes}m {seconds}s ago"
            
            return resource_dict
        except Exception as e:
            return {"error": f"Failed to get {resource_type}/{resource_name}: {str(e)}"}
