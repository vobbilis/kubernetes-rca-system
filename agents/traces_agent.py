from agents.base_agent import BaseAgent

class TracesAgent(BaseAgent):
    """
    Agent specialized in analyzing distributed traces.
    Focuses on request paths, latency, and inter-service communication.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the traces agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        super().__init__(k8s_client)
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Analyze traces data for the specified namespace.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the traces analysis
        """
        self.reset()
        
        try:
            # Set the context if provided
            if context:
                self.k8s_client.set_context(context)
            
            # Note: In a real implementation, this would extract traces from
            # a tracing backend like Jaeger, Zipkin, or OpenTelemetry.
            # For this implementation, we'll focus on detecting if tracing 
            # is enabled and providing recommendations.
            
            # Check if common tracing platforms are deployed
            jaeger_deployed = self._check_for_tracing_platform('jaeger')
            zipkin_deployed = self._check_for_tracing_platform('zipkin')
            otel_deployed = self._check_for_tracing_platform('opentelemetry')
            
            if not any([jaeger_deployed, zipkin_deployed, otel_deployed]):
                self.add_reasoning_step(
                    observation="No distributed tracing platform detected in the cluster",
                    conclusion="Unable to analyze traces without a tracing platform"
                )
                
                self.add_finding(
                    component="Tracing Infrastructure",
                    issue="No distributed tracing platform detected",
                    severity="medium",
                    evidence="No Jaeger, Zipkin, or OpenTelemetry collectors found",
                    recommendation="Deploy a distributed tracing solution like Jaeger or OpenTelemetry to enable trace analysis"
                )
                
                # Check if applications are instrumented for tracing
                self._check_for_tracing_instrumentation(namespace)
                
                return self.get_results()
            
            # Identify which tracing platform is in use
            tracing_platform = 'jaeger' if jaeger_deployed else 'zipkin' if zipkin_deployed else 'opentelemetry'
            
            self.add_reasoning_step(
                observation=f"Detected {tracing_platform} tracing platform",
                conclusion="Will analyze trace data from this platform"
            )
            
            # Check which services in the namespace are instrumented for tracing
            instrumented_services = self._check_for_tracing_instrumentation(namespace)
            
            if not instrumented_services:
                self.add_reasoning_step(
                    observation=f"No services in namespace {namespace} appear to be instrumented for tracing",
                    conclusion="Unable to analyze traces without instrumented services"
                )
                
                self.add_finding(
                    component="Service Instrumentation",
                    issue=f"No services in namespace {namespace} appear to be instrumented for tracing",
                    severity="medium",
                    evidence="No tracing environment variables or configuration detected in deployments",
                    recommendation="Instrument your services for distributed tracing to enable cross-service request analysis"
                )
                
                return self.get_results()
            
            # In a real implementation, the following would query the tracing backend
            # for actual trace data. Here we'll simulate finding some common issues.
            
            # Simulate checking for high-latency traces
            self._analyze_latency_issues(namespace, instrumented_services)
            
            # Simulate checking for error traces
            self._analyze_error_traces(namespace, instrumented_services)
            
            # Simulate checking for service dependencies
            self._analyze_service_dependencies(namespace, instrumented_services)
            
            return self.get_results()
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during traces analysis: {str(e)}",
                conclusion="Unable to complete traces analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _check_for_tracing_platform(self, platform_name):
        """
        Check if a specific tracing platform is deployed in the cluster.
        
        Args:
            platform_name: Name of the tracing platform to check for
            
        Returns:
            bool: True if the platform is deployed, False otherwise
        """
        # In a real implementation, this would search for deployments, services,
        # and other resources related to the tracing platform.
        # For simplicity, we'll just check for services with the platform name.
        
        try:
            # Search all namespaces for services related to the platform
            platform_services = self.k8s_client.get_services_by_label(f'app={platform_name}')
            collector_services = self.k8s_client.get_services_by_label(f'app={platform_name}-collector')
            query_services = self.k8s_client.get_services_by_label(f'app={platform_name}-query')
            
            # Check if any related services were found
            return len(platform_services) > 0 or len(collector_services) > 0 or len(query_services) > 0
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error checking for {platform_name}: {str(e)}",
                conclusion=f"Unable to determine if {platform_name} is deployed"
            )
            return False
    
    def _check_for_tracing_instrumentation(self, namespace):
        """
        Check which services in the namespace are instrumented for tracing.
        
        Args:
            namespace: The Kubernetes namespace to check
            
        Returns:
            list: Names of services that appear to be instrumented for tracing
        """
        instrumented_services = []
        
        try:
            # Get deployments in the namespace
            deployments = self.k8s_client.get_deployments(namespace)
            
            for deployment in deployments:
                deployment_name = deployment['metadata']['name']
                containers = deployment['spec']['template']['spec']['containers']
                
                for container in containers:
                    # Check for common tracing environment variables
                    env_vars = container.get('env', [])
                    
                    tracing_vars = [
                        var for var in env_vars if any(trace_key in var.get('name', '').lower() 
                                                    for trace_key in ['jaeger', 'zipkin', 'tracing', 'otel', 'opentelemetry'])
                    ]
                    
                    if tracing_vars:
                        instrumented_services.append(deployment_name)
                        break
            
            if instrumented_services:
                self.add_reasoning_step(
                    observation=f"Found {len(instrumented_services)} services with tracing instrumentation",
                    conclusion="These services can be analyzed for distributed traces"
                )
            else:
                self.add_reasoning_step(
                    observation="No services with tracing instrumentation found",
                    conclusion="Unable to analyze traces without instrumented services"
                )
                
                self.add_finding(
                    component="Tracing Configuration",
                    issue="No services are instrumented for distributed tracing",
                    severity="low",
                    evidence="No tracing environment variables found in service configurations",
                    recommendation="Add tracing instrumentation to your services for better observability"
                )
            
            return instrumented_services
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error checking for tracing instrumentation: {str(e)}",
                conclusion="Unable to determine which services are instrumented for tracing"
            )
            return []
    
    def _analyze_latency_issues(self, namespace, instrumented_services):
        """
        Analyze traces for latency issues.
        In a real implementation, this would query the tracing backend.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            instrumented_services: List of services instrumented for tracing
        """
        # Note: This is a simulated implementation. In a real system, you would
        # query the tracing backend for actual trace data.
        
        self.add_reasoning_step(
            observation=f"Checking for high-latency traces in {len(instrumented_services)} services",
            conclusion="Beginning latency analysis"
        )
        
        # For demonstration purposes, let's assume we find some high-latency traces
        # In a real implementation, you would actually fetch and analyze real trace data
        
        # Example finding for a service with high latency
        if instrumented_services:
            # Just use the first service as an example
            service_name = instrumented_services[0]
            
            self.add_finding(
                component=f"Service/{service_name}",
                issue="High latency detected in service calls",
                severity="medium",
                evidence="Trace analysis shows p95 latency above 500ms for HTTP GET operations",
                recommendation="Optimize database queries, add caching, or scale the service horizontally"
            )
            
            self.add_reasoning_step(
                observation=f"Detected high latency in {service_name} service",
                conclusion="Service performance may be affecting overall application responsiveness"
            )
        
        # Check for slow dependencies
        if len(instrumented_services) >= 2:
            # Use two different services as an example
            service_a = instrumented_services[0]
            service_b = instrumented_services[1]
            
            self.add_finding(
                component=f"Service/{service_a}→{service_b}",
                issue=f"Slow communication between {service_a} and {service_b}",
                severity="medium",
                evidence="Trace analysis shows high latency (>200ms) in calls from service_a to service_b",
                recommendation="Investigate network issues, optimize the API between these services, or consider co-locating them"
            )
            
            self.add_reasoning_step(
                observation=f"Detected slow communication between {service_a} and {service_b}",
                conclusion="Inter-service communication may be a bottleneck"
            )
    
    def _analyze_error_traces(self, namespace, instrumented_services):
        """
        Analyze traces for error paths.
        In a real implementation, this would query the tracing backend.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            instrumented_services: List of services instrumented for tracing
        """
        # Note: This is a simulated implementation. In a real system, you would
        # query the tracing backend for actual trace data.
        
        self.add_reasoning_step(
            observation=f"Checking for error traces in {len(instrumented_services)} services",
            conclusion="Beginning error path analysis"
        )
        
        # For demonstration purposes, let's assume we find some error traces
        # In a real implementation, you would actually fetch and analyze real trace data
        
        # Example finding for a service with errors
        if instrumented_services:
            # Just use the first service as an example
            service_name = instrumented_services[0]
            
            self.add_finding(
                component=f"Service/{service_name}",
                issue="Error traces detected in service",
                severity="high",
                evidence="5% of traces show HTTP 500 responses in the past hour",
                recommendation="Check service logs for corresponding errors and fix the underlying issue"
            )
            
            self.add_reasoning_step(
                observation=f"Detected error traces in {service_name} service",
                conclusion="Service is experiencing errors that may affect user experience"
            )
        
        # Check for cascading failures
        if len(instrumented_services) >= 3:
            # Use three different services as an example
            service_a = instrumented_services[0]
            service_b = instrumented_services[1]
            service_c = instrumented_services[2]
            
            self.add_finding(
                component=f"Services/{service_a}→{service_b}→{service_c}",
                issue="Cascading failures detected in service chain",
                severity="critical",
                evidence=f"Errors in {service_c} are causing failures in {service_b} and {service_a}",
                recommendation="Implement circuit breakers and fallback mechanisms to prevent cascading failures"
            )
            
            self.add_reasoning_step(
                observation=f"Detected cascading failures from {service_c} to {service_a}",
                conclusion="Failure isolation mechanisms may be missing in the service architecture"
            )
    
    def _analyze_service_dependencies(self, namespace, instrumented_services):
        """
        Analyze traces to understand service dependencies.
        In a real implementation, this would query the tracing backend.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            instrumented_services: List of services instrumented for tracing
        """
        # Note: This is a simulated implementation. In a real system, you would
        # query the tracing backend for actual trace data.
        
        self.add_reasoning_step(
            observation=f"Analyzing service dependencies among {len(instrumented_services)} services",
            conclusion="Beginning dependency analysis"
        )
        
        # For demonstration purposes, let's assume we find some dependency issues
        # In a real implementation, you would actually fetch and analyze real trace data
        
        # Example finding for service dependencies
        if len(instrumented_services) >= 2:
            # Use different services as examples
            service_a = instrumented_services[0]
            service_b = instrumented_services[len(instrumented_services) // 2] if len(instrumented_services) > 1 else instrumented_services[0]
            
            self.add_finding(
                component=f"Service/{service_a}",
                issue=f"High dependency on {service_b}",
                severity="medium",
                evidence=f"{service_a} makes frequent calls to {service_b}, creating a tight coupling",
                recommendation="Consider implementing caching, circuit breakers, or redesigning the interaction pattern"
            )
            
            self.add_reasoning_step(
                observation=f"Detected high dependency of {service_a} on {service_b}",
                conclusion="Service coupling may lead to reliability issues if the dependency fails"
            )
        
        # Check for circular dependencies
        if len(instrumented_services) >= 3:
            # Use three different services as an example
            service_a = instrumented_services[0]
            service_b = instrumented_services[1]
            service_c = instrumented_services[2]
            
            self.add_finding(
                component=f"Services/{service_a}↔{service_b}↔{service_c}",
                issue="Circular dependency detected between services",
                severity="high",
                evidence=f"Traces show a circular call pattern: {service_a} → {service_b} → {service_c} → {service_a}",
                recommendation="Refactor the service architecture to remove circular dependencies"
            )
            
            self.add_reasoning_step(
                observation=f"Detected circular dependency between {service_a}, {service_b}, and {service_c}",
                conclusion="Circular dependencies may lead to deadlocks and complicate scaling"
            )
