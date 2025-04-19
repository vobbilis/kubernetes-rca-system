import re
from agents.base_agent import BaseAgent

class LogsAgent(BaseAgent):
    """
    Agent specialized in analyzing Kubernetes logs data.
    Focuses on error detection, pattern recognition, and log analysis.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the logs agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        super().__init__(k8s_client)
        
        # Common error patterns to look for in logs
        self.error_patterns = {
            'oom_kill': r'(Out of memory|OOMKilled|Killed|signal: killed)',
            'connection_refused': r'(Connection refused|connect: connection refused)',
            'permission_denied': r'(Permission denied|Forbidden|Access denied)',
            'timeout': r'(timeout|Timeout|timed out|ETIMEDOUT)',
            'crash_loop': r'(CrashLoopBackOff|Back-off restarting)',
            'api_error': r'(API server error|StatusCode=5\d\d)',
            'volume_mount': r'(Unable to mount volumes|MountVolume.SetUp failed)',
            'image_pull': r'(ErrImagePull|ImagePullBackOff)',
            'dns_resolution': r'(DNS resolution failed|could not resolve)',
            'authentication': r'(Unauthorized|Authentication failed)',
            'config_error': r'(Invalid configuration|ConfigMap not found|Secret not found)',
            'internal_server_error': r'(internal server error|InternalServerError|500 Internal Server Error)',
            'exception': r'(Exception|Error|Traceback|FATAL|CRITICAL|Panic|panic:)'
        }
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Analyze logs data for the specified namespace.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the logs analysis
        """
        self.reset()
        
        try:
            # Set the context if provided
            if context:
                self.k8s_client.set_context(context)
            
            # Get pods in the namespace
            pods = self.k8s_client.get_pods(namespace)
            
            if not pods:
                self.add_reasoning_step(
                    observation=f"No pods found in namespace {namespace}",
                    conclusion="Unable to analyze logs as no pods were found"
                )
                return self.get_results()
            
            self.add_reasoning_step(
                observation=f"Found {len(pods)} pods in namespace {namespace}",
                conclusion="Beginning logs analysis for each pod"
            )
            
            # Get recently terminated pods
            terminated_pods = self.k8s_client.get_recently_terminated_pods(namespace)
            if terminated_pods:
                self.add_reasoning_step(
                    observation=f"Found {len(terminated_pods)} recently terminated pods",
                    conclusion="Will analyze logs from terminated pods as well"
                )
                pods.extend(terminated_pods)
            
            # Analyze logs for each pod
            pod_log_issues = []
            
            for pod in pods:
                pod_name = pod['metadata']['name']
                containers = pod['spec']['containers']
                
                for container in containers:
                    container_name = container['name']
                    
                    # Get logs for this container
                    logs = self.k8s_client.get_pod_logs(pod_name, namespace, container_name)
                    
                    if logs:
                        # Analyze container logs
                        self._analyze_container_logs(pod_name, container_name, logs)
                        
                        # Check for specific container issues
                        issues = self._check_container_status(pod, container_name)
                        if issues:
                            pod_log_issues.append((pod_name, container_name, issues))
            
            # Analyze pod status and conditions
            self._analyze_pod_conditions(pods)
            
            # Analyze init container failures
            self._analyze_init_containers(pods)
            
            # Check for pods with no logs
            self._check_for_no_logs(pods)
            
            # Return the analysis results
            return self.get_results()
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during logs analysis: {str(e)}",
                conclusion="Unable to complete logs analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _analyze_container_logs(self, pod_name, container_name, logs):
        """
        Analyze logs for a specific container.
        
        Args:
            pod_name: Name of the pod
            container_name: Name of the container
            logs: Container logs as string
        """
        if not logs:
            self.add_reasoning_step(
                observation=f"No logs available for {pod_name}/{container_name}",
                conclusion="Unable to analyze logs for this container"
            )
            return
        
        log_lines = logs.splitlines()
        self.add_reasoning_step(
            observation=f"Analyzing {len(log_lines)} log lines for {pod_name}/{container_name}",
            conclusion="Beginning log pattern analysis"
        )
        
        # Check for common error patterns
        error_matches = {}
        for error_type, pattern in self.error_patterns.items():
            matches = [line for line in log_lines if re.search(pattern, line, re.IGNORECASE)]
            if matches:
                error_matches[error_type] = matches
        
        # Report on findings
        if error_matches:
            for error_type, matches in error_matches.items():
                severity = self._determine_error_severity(error_type)
                
                # Limit number of example lines to avoid overwhelming the report
                example_lines = matches[:3]
                example_text = "\n".join([f"- {line[:200]}..." if len(line) > 200 else f"- {line}" for line in example_lines])
                
                if len(matches) > 3:
                    example_text += f"\n- ... and {len(matches) - 3} more similar errors"
                
                self.add_finding(
                    component=f"Pod/{pod_name}/{container_name}",
                    issue=f"Detected {len(matches)} instances of {self._format_error_type(error_type)} in logs",
                    severity=severity,
                    evidence=f"Log entries:\n{example_text}",
                    recommendation=self._get_recommendation_for_error(error_type)
                )
                
                self.add_reasoning_step(
                    observation=f"Found {len(matches)} log entries matching {error_type} pattern in {pod_name}/{container_name}",
                    conclusion=f"Container is experiencing {self._format_error_type(error_type)} issues"
                )
        else:
            self.add_reasoning_step(
                observation=f"No error patterns detected in logs for {pod_name}/{container_name}",
                conclusion="Container logs appear normal"
            )
    
    def _check_container_status(self, pod, container_name):
        """
        Check the status of a container in a pod.
        
        Args:
            pod: Pod data
            container_name: Name of the container
            
        Returns:
            list: Issues found with the container
        """
        issues = []
        
        # Get container status from pod status
        container_statuses = pod['status'].get('containerStatuses', [])
        init_container_statuses = pod['status'].get('initContainerStatuses', [])
        
        # Combine both types of container statuses
        all_statuses = container_statuses + init_container_statuses
        
        # Find the status for this container
        container_status = next((status for status in all_statuses if status['name'] == container_name), None)
        
        if not container_status:
            return issues
        
        # Check for restarts
        restart_count = container_status.get('restartCount', 0)
        if restart_count > 5:
            issues.append(f"High restart count ({restart_count})")
            
            self.add_finding(
                component=f"Pod/{pod['metadata']['name']}/{container_name}",
                issue=f"Container has restarted {restart_count} times",
                severity="high" if restart_count > 10 else "medium",
                evidence=f"Container {container_name} in pod {pod['metadata']['name']} has a restart count of {restart_count}",
                recommendation="Investigate logs for crash causes and ensure the container is properly configured"
            )
        
        # Check last state if container is not ready
        if not container_status.get('ready', True):
            last_state = container_status.get('lastState', {})
            
            if 'terminated' in last_state:
                terminated = last_state['terminated']
                exit_code = terminated.get('exitCode', 0)
                reason = terminated.get('reason', 'Unknown')
                
                if exit_code != 0:
                    issues.append(f"Container terminated with exit code {exit_code} ({reason})")
                    
                    self.add_finding(
                        component=f"Pod/{pod['metadata']['name']}/{container_name}",
                        issue=f"Container terminated with non-zero exit code {exit_code}",
                        severity="high",
                        evidence=f"Termination reason: {reason}",
                        recommendation="Check container logs for error details and fix the underlying issue"
                    )
            
            elif 'waiting' in last_state:
                waiting = last_state['waiting']
                reason = waiting.get('reason', 'Unknown')
                message = waiting.get('message', '')
                
                issues.append(f"Container in waiting state: {reason}")
                
                self.add_finding(
                    component=f"Pod/{pod['metadata']['name']}/{container_name}",
                    issue=f"Container is in waiting state with reason: {reason}",
                    severity="medium",
                    evidence=f"Waiting message: {message}",
                    recommendation="Address the issue preventing the container from starting"
                )
        
        return issues
    
    def _analyze_pod_conditions(self, pods):
        """
        Analyze pod conditions for issues.
        
        Args:
            pods: List of pod data
        """
        condition_issues = []
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            conditions = pod['status'].get('conditions', [])
            
            # Check for unschedulable pods
            for condition in conditions:
                condition_type = condition.get('type', '')
                status = condition.get('status', '')
                reason = condition.get('reason', '')
                message = condition.get('message', '')
                
                if condition_type == 'PodScheduled' and status == 'False':
                    condition_issues.append((pod_name, 'Unschedulable', reason, message))
                    
                    self.add_finding(
                        component=f"Pod/{pod_name}",
                        issue=f"Pod cannot be scheduled",
                        severity="high",
                        evidence=f"Reason: {reason}, Message: {message}",
                        recommendation="Check node resources, taints, tolerations, and node selectors"
                    )
                
                elif condition_type == 'Ready' and status == 'False':
                    condition_issues.append((pod_name, 'Not Ready', reason, message))
                    
                    self.add_finding(
                        component=f"Pod/{pod_name}",
                        issue=f"Pod is not in Ready state",
                        severity="medium",
                        evidence=f"Reason: {reason}, Message: {message}",
                        recommendation="Investigate container statuses and logs for errors"
                    )
        
        if condition_issues:
            self.add_reasoning_step(
                observation=f"Found {len(condition_issues)} pods with condition issues",
                conclusion="Pod conditions indicate scheduling or readiness problems"
            )
        else:
            self.add_reasoning_step(
                observation="No pod condition issues detected",
                conclusion="All pods appear to be properly scheduled and ready"
            )
    
    def _analyze_init_containers(self, pods):
        """
        Analyze init container issues.
        
        Args:
            pods: List of pod data
        """
        init_container_issues = []
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            init_container_statuses = pod['status'].get('initContainerStatuses', [])
            
            for status in init_container_statuses:
                container_name = status.get('name', '')
                ready = status.get('ready', False)
                
                if not ready:
                    state = status.get('state', {})
                    
                    if 'waiting' in state:
                        waiting = state['waiting']
                        reason = waiting.get('reason', 'Unknown')
                        message = waiting.get('message', '')
                        
                        init_container_issues.append((pod_name, container_name, reason, message))
                        
                        self.add_finding(
                            component=f"Pod/{pod_name}/init/{container_name}",
                            issue=f"Init container is waiting with reason: {reason}",
                            severity="high",
                            evidence=f"Message: {message}",
                            recommendation="Check init container logs and configuration"
                        )
                    
                    elif 'terminated' in state:
                        terminated = state['terminated']
                        exit_code = terminated.get('exitCode', 0)
                        reason = terminated.get('reason', 'Unknown')
                        
                        if exit_code != 0:
                            init_container_issues.append((pod_name, container_name, reason, f"Exit code: {exit_code}"))
                            
                            self.add_finding(
                                component=f"Pod/{pod_name}/init/{container_name}",
                                issue=f"Init container terminated with non-zero exit code {exit_code}",
                                severity="high",
                                evidence=f"Termination reason: {reason}",
                                recommendation="Check init container logs for error details"
                            )
        
        if init_container_issues:
            self.add_reasoning_step(
                observation=f"Found {len(init_container_issues)} init container issues",
                conclusion="Init container failures are preventing pods from starting"
            )
        else:
            self.add_reasoning_step(
                observation="No init container issues detected",
                conclusion="All init containers appear to be functioning correctly"
            )
    
    def _check_for_no_logs(self, pods):
        """
        Check for pods that should have logs but don't.
        
        Args:
            pods: List of pod data
        """
        # This is a simplified implementation; in a real system, you would
        # need more sophisticated logic to determine if a pod should have logs
        for pod in pods:
            pod_name = pod['metadata']['name']
            phase = pod['status'].get('phase', '')
            
            # Only check running pods that have been up for some time
            if phase == 'Running':
                containers = pod['spec']['containers']
                
                for container in containers:
                    container_name = container['name']
                    logs = self.k8s_client.get_pod_logs(pod_name, pod['metadata']['namespace'], container_name)
                    
                    if not logs:
                        # Check when the pod started
                        start_time = pod['status'].get('startTime', '')
                        current_time = self.k8s_client.get_current_time()
                        
                        # If pod has been running for more than 5 minutes but has no logs
                        # Note: This is a simplified check; in reality, you would parse and compare the times
                        if start_time and (current_time - start_time).total_seconds() > 300:
                            self.add_finding(
                                component=f"Pod/{pod_name}/{container_name}",
                                issue=f"Container has been running for over 5 minutes but has no logs",
                                severity="medium",
                                evidence=f"No log output detected for container {container_name}",
                                recommendation="Verify the application is properly writing to stdout/stderr and not failing silently"
                            )
                            
                            self.add_reasoning_step(
                                observation=f"No logs found for {pod_name}/{container_name} despite running state",
                                conclusion="Container may be failing silently or not properly logging to stdout/stderr"
                            )
    
    def _determine_error_severity(self, error_type):
        """
        Determine the severity level for a specific error type.
        
        Args:
            error_type: Type of error
            
        Returns:
            str: Severity level (critical, high, medium, low, info)
        """
        high_severity_errors = ['oom_kill', 'crash_loop', 'image_pull']
        medium_severity_errors = ['connection_refused', 'timeout', 'volume_mount', 'dns_resolution', 'internal_server_error']
        low_severity_errors = ['permission_denied', 'authentication', 'config_error']
        
        if error_type in high_severity_errors:
            return "high"
        elif error_type in medium_severity_errors:
            return "medium"
        elif error_type in low_severity_errors:
            return "low"
        else:
            return "info"
    
    def _format_error_type(self, error_type):
        """
        Format error type for display.
        
        Args:
            error_type: Type of error
            
        Returns:
            str: Formatted error type
        """
        return ' '.join(word.capitalize() for word in error_type.split('_'))
    
    def _get_recommendation_for_error(self, error_type):
        """
        Get a recommendation based on the error type.
        
        Args:
            error_type: Type of error
            
        Returns:
            str: Recommendation
        """
        recommendations = {
            'oom_kill': "Increase memory limits for the container or optimize the application's memory usage",
            'connection_refused': "Check network policies, service endpoints, and ensure the target service is running",
            'permission_denied': "Verify RBAC permissions, service account settings, and security contexts",
            'timeout': "Check for network issues, increase timeout values, or optimize the slow operation",
            'crash_loop': "Investigate container logs for crash causes and fix the underlying application issue",
            'api_error': "Check for Kubernetes API server issues or problems with the client configuration",
            'volume_mount': "Verify PVC status, storage class availability, and volume permissions",
            'image_pull': "Ensure the image exists, credentials are correct, and network connectivity to the registry",
            'dns_resolution': "Check CoreDNS/kube-dns functionality and network policies that might block DNS",
            'authentication': "Verify credentials, tokens, and authentication configuration",
            'config_error': "Check that all required ConfigMaps and Secrets exist and are correctly referenced",
            'internal_server_error': "Investigate server-side issues in the dependent service",
            'exception': "Debug the application code to fix the exception"
        }
        
        return recommendations.get(error_type, "Investigate the logs in detail to identify the root cause")
