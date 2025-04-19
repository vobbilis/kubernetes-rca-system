import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Configure logging to a file
logging.basicConfig(
    filename='resource_analysis.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('resource_analyzer')

class ResourceAnalyzer:
    """
    Analyzes Kubernetes resources to detect issues and misconfigurations.
    Provides detailed logging of the analysis process and findings.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the resource analyzer with a Kubernetes client.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        self.k8s_client = k8s_client
        self.findings = []
        self.reasoning_steps = []
        
    def analyze_namespace_resources(self, namespace: str) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of all resources in a namespace.
        
        Args:
            namespace: The namespace to analyze
            
        Returns:
            Dict containing analysis results
        """
        logger.info(f"Starting comprehensive resource analysis for namespace: {namespace}")
        
        # Get all resources in the namespace
        services = self.k8s_client.get_services(namespace)
        deployments = self.k8s_client.get_deployments(namespace)
        pods = self.k8s_client.get_pods(namespace)
        events = self.k8s_client.get_events(namespace)
        
        # Additional resource types
        try:
            statefulsets_result = self.k8s_client._run_kubectl_command(["get", "statefulsets", "-n", namespace, "-o", "json"])
            statefulsets = json.loads(statefulsets_result['output'])['items'] if statefulsets_result['success'] else []
        except Exception as e:
            logger.error(f"Error fetching StatefulSets: {e}")
            statefulsets = []
            
        try:
            daemonsets_result = self.k8s_client._run_kubectl_command(["get", "daemonsets", "-n", namespace, "-o", "json"])
            daemonsets = json.loads(daemonsets_result['output'])['items'] if daemonsets_result['success'] else []
        except Exception as e:
            logger.error(f"Error fetching DaemonSets: {e}")
            daemonsets = []
            
        try:
            cronjobs_result = self.k8s_client._run_kubectl_command(["get", "cronjobs", "-n", namespace, "-o", "json"])
            cronjobs = json.loads(cronjobs_result['output'])['items'] if cronjobs_result['success'] else []
        except Exception as e:
            logger.error(f"Error fetching CronJobs: {e}")
            cronjobs = []
        
        logger.info(f"Found {len(services)} services, {len(deployments)} deployments, {len(statefulsets)} statefulsets, {len(daemonsets)} daemonsets, {len(pods)} pods, {len(events)} events in namespace {namespace}")
        
        # Analyze all resources
        self._analyze_services(services, namespace)
        self._analyze_deployments(deployments, namespace)
        self._analyze_statefulsets(statefulsets, namespace)
        self._analyze_daemonsets(daemonsets, namespace)
        self._analyze_pods(pods, namespace)
        self._correlate_with_events(events, namespace)
        
        # Summarize findings
        return {
            'namespace': namespace,
            'resource_count': {
                'services': len(services),
                'deployments': len(deployments),
                'statefulsets': len(statefulsets),
                'daemonsets': len(daemonsets),
                'pods': len(pods)
            },
            'findings': self.findings,
            'reasoning_steps': self.reasoning_steps
        }
    
    def _analyze_services(self, services: List[Dict], namespace: str) -> None:
        """
        Analyze services for potential issues.
        
        Args:
            services: List of service data
            namespace: The namespace being analyzed
        """
        logger.info(f"Analyzing {len(services)} services in namespace {namespace}")
        
        for service in services:
            service_name = service['metadata']['name']
            service_type = service['spec'].get('type', 'ClusterIP')
            selector = service['spec'].get('selector', {})
            
            logger.info(f"Analyzing service {service_name} of type {service_type}")
            
            # Check if service has selectors
            if not selector:
                self.add_finding(
                    component=f"Service/{service_name}",
                    issue="Service has no selector",
                    severity="medium",
                    evidence="No pod selector specified in service definition",
                    recommendation="Add appropriate selectors to match target pods"
                )
                continue
                
            # Check if selectors match any pods
            matching_pods = self._find_matching_pods(namespace, selector)
            
            if not matching_pods:
                self.add_finding(
                    component=f"Service/{service_name}",
                    issue="Service selector matches no pods",
                    severity="high",
                    evidence=f"Selector {selector} does not match any pods in the namespace",
                    recommendation="Verify selector labels or check if pods are running"
                )
            else:
                logger.info(f"Service {service_name} matches {len(matching_pods)} pods")
                
                # Check for unhealthy pods that would affect the service
                unhealthy_pods = [p for p in matching_pods if not self._is_pod_healthy(p)]
                if unhealthy_pods:
                    pod_names = [p['metadata']['name'] for p in unhealthy_pods]
                    self.add_finding(
                        component=f"Service/{service_name}",
                        issue="Service targets unhealthy pods",
                        severity="high",
                        evidence=f"Pods {', '.join(pod_names)} matched by this service are unhealthy",
                        recommendation="Investigate pod issues to restore service functionality"
                    )
    
    def _analyze_deployments(self, deployments: List[Dict], namespace: str) -> None:
        """
        Analyze deployments for potential issues.
        
        Args:
            deployments: List of deployment data
            namespace: The namespace being analyzed
        """
        logger.info(f"Analyzing {len(deployments)} deployments in namespace {namespace}")
        
        for deployment in deployments:
            deployment_name = deployment['metadata']['name']
            replicas = deployment['spec'].get('replicas', 0)
            available_replicas = deployment['status'].get('availableReplicas', 0)
            ready_replicas = deployment['status'].get('readyReplicas', 0)
            unavailable_replicas = deployment['status'].get('unavailableReplicas', 0)
            
            logger.info(f"Analyzing deployment {deployment_name} with {replicas} desired replicas, {available_replicas} available, {ready_replicas} ready, {unavailable_replicas} unavailable")
            
            # Check for deployments with insufficient replicas
            if ready_replicas < replicas:
                self.add_finding(
                    component=f"Deployment/{deployment_name}",
                    issue=f"Deployment has {ready_replicas}/{replicas} ready replicas",
                    severity="high" if ready_replicas == 0 else "medium",
                    evidence=f"Status: {ready_replicas} ready, {available_replicas} available, {unavailable_replicas} unavailable of {replicas} desired",
                    recommendation="Investigate pod creation issues or container problems"
                )
                
            # Check for deployments with incorrect selector configuration
            try:
                selector = deployment['spec'].get('selector', {}).get('matchLabels', {})
                template_labels = deployment['spec'].get('template', {}).get('metadata', {}).get('labels', {})
                
                # Check if selector matches template labels
                for key, value in selector.items():
                    if key not in template_labels or template_labels[key] != value:
                        self.add_finding(
                            component=f"Deployment/{deployment_name}",
                            issue="Deployment selector doesn't match template labels",
                            severity="high",
                            evidence=f"Selector {selector} doesn't match pod template labels {template_labels}",
                            recommendation="Correct the selector to match pod template labels"
                        )
                        break
            except Exception as e:
                logger.error(f"Error analyzing deployment {deployment_name} selectors: {e}")
    
    def _analyze_statefulsets(self, statefulsets: List[Dict], namespace: str) -> None:
        """
        Analyze statefulsets for potential issues.
        
        Args:
            statefulsets: List of statefulset data
            namespace: The namespace being analyzed
        """
        logger.info(f"Analyzing {len(statefulsets)} statefulsets in namespace {namespace}")
        
        for statefulset in statefulsets:
            name = statefulset['metadata']['name']
            replicas = statefulset['spec'].get('replicas', 0)
            ready_replicas = statefulset['status'].get('readyReplicas', 0)
            
            logger.info(f"Analyzing statefulset {name} with {replicas} desired replicas, {ready_replicas} ready")
            
            # Check for statefulsets with insufficient replicas
            if ready_replicas < replicas:
                self.add_finding(
                    component=f"StatefulSet/{name}",
                    issue=f"StatefulSet has {ready_replicas}/{replicas} ready replicas",
                    severity="high" if ready_replicas == 0 else "medium",
                    evidence=f"Status: {ready_replicas} ready of {replicas} desired",
                    recommendation="Check for persistent volume issues or pod scheduling problems"
                )
                
            # Check for volume mounts in spec
            volume_claim_templates = statefulset['spec'].get('volumeClaimTemplates', [])
            if not volume_claim_templates:
                self.add_finding(
                    component=f"StatefulSet/{name}",
                    issue="StatefulSet doesn't define persistent volume claim templates",
                    severity="low",
                    evidence="No volumeClaimTemplates found in the StatefulSet definition",
                    recommendation="Consider adding persistent storage for stateful applications"
                )
    
    def _analyze_daemonsets(self, daemonsets: List[Dict], namespace: str) -> None:
        """
        Analyze daemonsets for potential issues.
        
        Args:
            daemonsets: List of daemonset data
            namespace: The namespace being analyzed
        """
        logger.info(f"Analyzing {len(daemonsets)} daemonsets in namespace {namespace}")
        
        for daemonset in daemonsets:
            name = daemonset['metadata']['name']
            desired_number = daemonset['status'].get('desiredNumberScheduled', 0)
            current_number = daemonset['status'].get('currentNumberScheduled', 0)
            ready_number = daemonset['status'].get('numberReady', 0)
            
            logger.info(f"Analyzing daemonset {name} with {desired_number} desired pods, {current_number} scheduled, {ready_number} ready")
            
            # Check for daemonsets with insufficient pods
            if ready_number < desired_number:
                self.add_finding(
                    component=f"DaemonSet/{name}",
                    issue=f"DaemonSet has {ready_number}/{desired_number} ready pods",
                    severity="high" if ready_number == 0 else "medium",
                    evidence=f"Status: {ready_number} ready, {current_number} scheduled of {desired_number} desired",
                    recommendation="Check for node taints or affinity issues"
                )
    
    def _analyze_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pods for potential issues.
        
        Args:
            pods: List of pod data
            namespace: The namespace being analyzed
        """
        logger.info(f"Analyzing {len(pods)} pods in namespace {namespace}")
        
        # Group pods by status for better analysis
        status_groups = {
            'pending': [],
            'running': [],
            'succeeded': [],
            'failed': [],
            'unknown': [],
            'crashloopbackoff': [],
            'imagepullbackoff': [],
            'containercreating': [],
            'error': [],
            'evicted': [],
            'init_crashloopbackoff': [],
            'not_ready': []
        }
        
        # Categorize pods
        for pod in pods:
            pod_name = pod['metadata']['name']
            phase = pod['status'].get('phase', 'Unknown')
            
            # Check pod status and categorize
            if phase == 'Pending':
                status_groups['pending'].append(pod)
            elif phase == 'Running':
                if not self._is_pod_healthy(pod):
                    container_statuses = pod['status'].get('containerStatuses', [])
                    init_container_statuses = pod['status'].get('initContainerStatuses', [])
                    all_statuses = container_statuses + init_container_statuses
                    
                    # Check for specific container issues
                    for status in all_statuses:
                        state = status.get('state', {})
                        
                        if 'waiting' in state:
                            reason = state['waiting'].get('reason', '')
                            
                            if reason == 'CrashLoopBackOff':
                                if status['name'].startswith('init-'):
                                    status_groups['init_crashloopbackoff'].append(pod)
                                else:
                                    status_groups['crashloopbackoff'].append(pod)
                                break
                            elif reason == 'ImagePullBackOff' or reason == 'ErrImagePull':
                                status_groups['imagepullbackoff'].append(pod)
                                break
                            elif reason == 'ContainerCreating':
                                status_groups['containercreating'].append(pod)
                                break
                        
                    # Check if pod is running but not ready
                    ready = True
                    for condition in pod['status'].get('conditions', []):
                        if condition.get('type') == 'Ready' and condition.get('status') != 'True':
                            ready = False
                            break
                            
                    if not ready:
                        status_groups['not_ready'].append(pod)
                else:
                    status_groups['running'].append(pod)
            elif phase == 'Succeeded':
                status_groups['succeeded'].append(pod)
            elif phase == 'Failed':
                status_groups['failed'].append(pod)
            elif phase == 'Unknown':
                status_groups['unknown'].append(pod)
            
            # Check for evicted pods
            if pod['status'].get('reason', '') == 'Evicted':
                status_groups['evicted'].append(pod)
                
            # Check for general error state
            container_statuses = pod['status'].get('containerStatuses', [])
            for status in container_statuses:
                if status.get('state', {}).get('terminated', {}).get('reason', '') == 'Error':
                    status_groups['error'].append(pod)
                    break
        
        # Log the status group counts
        log_msg = "Pod status breakdown: "
        for status, pods_list in status_groups.items():
            log_msg += f"{status}: {len(pods_list)}, "
        logger.info(log_msg)
        
        # Analyze each group
        self._analyze_pending_pods(status_groups['pending'], namespace)
        self._analyze_failing_pods(status_groups['failed'] + status_groups['error'], namespace)
        self._analyze_crashloop_pods(status_groups['crashloopbackoff'], namespace)
        self._analyze_imagepull_pods(status_groups['imagepullbackoff'], namespace)
        self._analyze_creating_pods(status_groups['containercreating'], namespace)
        self._analyze_init_crashloop_pods(status_groups['init_crashloopbackoff'], namespace)
        self._analyze_not_ready_pods(status_groups['not_ready'], namespace)
        self._analyze_evicted_pods(status_groups['evicted'], namespace)
        
        # Add summary finding if there are problematic pods
        problematic_count = sum(len(pods_list) for status, pods_list in status_groups.items() 
                              if status not in ['running', 'succeeded'])
        
        if problematic_count > 0:
            self.add_finding(
                component=f"Namespace/{namespace}",
                issue=f"Found {problematic_count} pods with issues",
                severity="high" if problematic_count > 5 else "medium",
                evidence=self._format_pod_status_evidence(status_groups),
                recommendation="Investigate pod issues based on their specific error states"
            )
    
    def _analyze_pending_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pending pods for scheduling issues.
        
        Args:
            pods: List of pending pod data
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} pending pods in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Check pod conditions for scheduling issues
            for condition in pod['status'].get('conditions', []):
                if condition.get('type') == 'PodScheduled' and condition.get('status') == 'False':
                    reason = condition.get('reason', '')
                    message = condition.get('message', '')
                    
                    if reason == 'Unschedulable':
                        self.add_finding(
                            component=f"Pod/{pod_name}",
                            issue="Pod cannot be scheduled",
                            severity="high",
                            evidence=f"Message: {message}",
                            recommendation="Check node resources, taints, tolerations, and node selectors"
                        )
                        
                        # Log detailed reasoning
                        logger.info(f"Pod {pod_name} unschedulable: {message}")
    
    def _analyze_failing_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze failed pods for root cause.
        
        Args:
            pods: List of failed pod data
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} failed/error pods in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Get container states
            container_statuses = pod['status'].get('containerStatuses', [])
            
            for status in container_statuses:
                container_name = status.get('name', '')
                state = status.get('state', {})
                last_state = status.get('lastState', {})
                
                # Check for terminated state with error
                if 'terminated' in state:
                    exit_code = state['terminated'].get('exitCode', 0)
                    reason = state['terminated'].get('reason', '')
                    message = state['terminated'].get('message', '')
                    
                    self.add_finding(
                        component=f"Pod/{pod_name}/{container_name}",
                        issue=f"Container terminated with exit code {exit_code}",
                        severity="high",
                        evidence=f"Reason: {reason}, Message: {message}",
                        recommendation="Check container logs and fix application errors"
                    )
                    
                    # Log container termination details
                    logger.info(f"Container {container_name} in pod {pod_name} terminated: exit code {exit_code}, reason: {reason}, message: {message}")
    
    def _analyze_crashloop_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze crashing pods.
        
        Args:
            pods: List of pod data in CrashLoopBackOff
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} crash looping pods in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Get container details
            container_statuses = pod['status'].get('containerStatuses', [])
            
            for status in container_statuses:
                container_name = status.get('name', '')
                restart_count = status.get('restartCount', 0)
                
                if restart_count > 0:
                    # Get last state termination info if available
                    last_state = status.get('lastState', {})
                    terminated = last_state.get('terminated', {})
                    exit_code = terminated.get('exitCode', 'unknown')
                    reason = terminated.get('reason', 'unknown')
                    
                    self.add_finding(
                        component=f"Pod/{pod_name}/{container_name}",
                        issue=f"Container in CrashLoopBackOff with {restart_count} restarts",
                        severity="high",
                        evidence=f"Last exit code: {exit_code}, reason: {reason}",
                        recommendation="Check container logs for application errors and fix the root cause"
                    )
                    
                    # Log crash details
                    logger.info(f"Container {container_name} in pod {pod_name} crash looping: {restart_count} restarts, last exit code: {exit_code}")
                    
                    # Get container logs if possible
                    try:
                        logs = self.k8s_client.get_pod_logs(pod_name, namespace, container_name, tail_lines=50)
                        if logs:
                            logger.info(f"Last 50 lines of logs for {pod_name}/{container_name}:\n{logs}")
                    except Exception as e:
                        logger.error(f"Error fetching logs for {pod_name}/{container_name}: {e}")
    
    def _analyze_imagepull_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pods with image pull issues.
        
        Args:
            pods: List of pod data with ImagePullBackOff
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} pods with image pull issues in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Get container details
            container_statuses = pod['status'].get('containerStatuses', [])
            
            for status in container_statuses:
                container_name = status.get('name', '')
                image = status.get('image', '')
                
                # Get waiting state info
                state = status.get('state', {})
                waiting = state.get('waiting', {})
                reason = waiting.get('reason', '')
                message = waiting.get('message', '')
                
                if reason in ['ImagePullBackOff', 'ErrImagePull']:
                    self.add_finding(
                        component=f"Pod/{pod_name}/{container_name}",
                        issue=f"Cannot pull image: {image}",
                        severity="high",
                        evidence=f"Message: {message}",
                        recommendation="Verify image name, tag, and registry credentials"
                    )
                    
                    # Log image pull details
                    logger.info(f"Image pull issue for {pod_name}/{container_name}: {message}")
    
    def _analyze_creating_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pods stuck in ContainerCreating.
        
        Args:
            pods: List of pod data in ContainerCreating
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} pods stuck in ContainerCreating in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Look for volume mounts that might be causing issues
            volumes = pod['spec'].get('volumes', [])
            pvc_volumes = [v for v in volumes if 'persistentVolumeClaim' in v]
            
            if pvc_volumes:
                pvc_names = [v.get('persistentVolumeClaim', {}).get('claimName', '') for v in pvc_volumes]
                pvc_names_str = ', '.join(pvc_names)
                
                self.add_finding(
                    component=f"Pod/{pod_name}",
                    issue="Pod stuck in ContainerCreating state",
                    severity="medium",
                    evidence=f"Pod uses PVCs: {pvc_names_str} which may be pending",
                    recommendation="Check PVC status and storage provisioner"
                )
            else:
                self.add_finding(
                    component=f"Pod/{pod_name}",
                    issue="Pod stuck in ContainerCreating state",
                    severity="medium",
                    evidence="Pod has been in ContainerCreating state for an extended period",
                    recommendation="Check for resource constraints or image pull issues"
                )
            
            # Log creating pod details
            logger.info(f"Pod {pod_name} stuck in ContainerCreating state")
    
    def _analyze_init_crashloop_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pods with init containers in CrashLoopBackOff.
        
        Args:
            pods: List of pod data with init containers in CrashLoopBackOff
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} pods with init container issues in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Get init container statuses
            init_container_statuses = pod['status'].get('initContainerStatuses', [])
            
            for status in init_container_statuses:
                container_name = status.get('name', '')
                restart_count = status.get('restartCount', 0)
                
                if restart_count > 0:
                    # Get last state termination info if available
                    last_state = status.get('lastState', {})
                    terminated = last_state.get('terminated', {})
                    exit_code = terminated.get('exitCode', 'unknown')
                    reason = terminated.get('reason', 'unknown')
                    
                    self.add_finding(
                        component=f"Pod/{pod_name}/{container_name}",
                        issue=f"Init container in CrashLoopBackOff with {restart_count} restarts",
                        severity="high",
                        evidence=f"Last exit code: {exit_code}, reason: {reason}",
                        recommendation="Check init container logs and fix initialization errors"
                    )
                    
                    # Log init container crash details
                    logger.info(f"Init container {container_name} in pod {pod_name} crash looping: {restart_count} restarts, last exit code: {exit_code}")
                    
                    # Get container logs if possible
                    try:
                        logs = self.k8s_client.get_pod_logs(pod_name, namespace, container_name, tail_lines=50)
                        if logs:
                            logger.info(f"Last 50 lines of logs for init container {pod_name}/{container_name}:\n{logs}")
                    except Exception as e:
                        logger.error(f"Error fetching logs for init container {pod_name}/{container_name}: {e}")
    
    def _analyze_not_ready_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze pods that are running but not ready.
        
        Args:
            pods: List of pod data that are running but not ready
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} pods that are running but not ready in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            
            # Check readiness probe configuration
            containers = pod['spec'].get('containers', [])
            for container in containers:
                container_name = container.get('name', '')
                readiness_probe = container.get('readinessProbe')
                
                if not readiness_probe:
                    self.add_finding(
                        component=f"Pod/{pod_name}/{container_name}",
                        issue="Container has no readiness probe",
                        severity="low",
                        evidence="No readiness probe specified in container definition",
                        recommendation="Add appropriate readiness probe to container"
                    )
                else:
                    # Container has readiness probe, check container status
                    container_statuses = pod['status'].get('containerStatuses', [])
                    container_status = next((s for s in container_statuses if s.get('name') == container_name), None)
                    
                    if container_status and not container_status.get('ready', False):
                        self.add_finding(
                            component=f"Pod/{pod_name}/{container_name}",
                            issue="Container not passing readiness probe",
                            severity="medium",
                            evidence="Container is running but failing readiness checks",
                            recommendation="Check application logs and fix readiness issues"
                        )
                        
                        # Log readiness probe failure details
                        logger.info(f"Container {container_name} in pod {pod_name} failing readiness probe")
    
    def _analyze_evicted_pods(self, pods: List[Dict], namespace: str) -> None:
        """
        Analyze evicted pods.
        
        Args:
            pods: List of evicted pod data
            namespace: The namespace being analyzed
        """
        if not pods:
            return
            
        logger.info(f"Analyzing {len(pods)} evicted pods in namespace {namespace}")
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            message = pod['status'].get('message', 'Unknown reason')
            
            self.add_finding(
                component=f"Pod/{pod_name}",
                issue="Pod has been evicted",
                severity="medium",
                evidence=f"Eviction message: {message}",
                recommendation="Check for resource constraints, particularly node disk pressure"
            )
            
            # Log eviction details
            logger.info(f"Pod {pod_name} evicted: {message}")
    
    def _correlate_with_events(self, events: List[Dict], namespace: str) -> None:
        """
        Correlate findings with Kubernetes events.
        
        Args:
            events: List of event data
            namespace: The namespace being analyzed
        """
        if not events:
            return
            
        logger.info(f"Correlating findings with {len(events)} events in namespace {namespace}")
        
        # Group events by involved object
        object_events = {}
        for event in events:
            involved_object = event.get('involvedObject', {})
            kind = involved_object.get('kind', '')
            name = involved_object.get('name', '')
            
            if kind and name:
                key = f"{kind}/{name}"
                if key not in object_events:
                    object_events[key] = []
                object_events[key].append(event)
        
        # Look for event patterns related to our findings
        for component, events_list in object_events.items():
            # Check if we already have findings for this component
            existing_findings = [f for f in self.findings if f['component'] == component]
            
            if existing_findings:
                # Enhance existing findings with event information
                for finding in existing_findings:
                    related_events = [e for e in events_list if self._is_event_related_to_finding(e, finding)]
                    if related_events:
                        # Add event information to evidence
                        event_messages = [f"{e.get('reason', '')}: {e.get('message', '')}" for e in related_events[:3]]
                        finding['evidence'] += f"\nRelated events: {' | '.join(event_messages)}"
            else:
                # Create new findings for important events without existing findings
                self._create_findings_from_events(component, events_list)
    
    def _is_event_related_to_finding(self, event: Dict, finding: Dict) -> bool:
        """
        Check if an event is related to a finding.
        
        Args:
            event: Event data
            finding: Finding data
            
        Returns:
            True if related, False otherwise
        """
        # Check if the event reason or message is related to the finding issue
        event_reason = event.get('reason', '').lower()
        event_message = event.get('message', '').lower()
        finding_issue = finding.get('issue', '').lower()
        
        # Common keywords for different types of issues
        relation_keywords = {
            'crash': ['backoff', 'crash', 'exit', 'fail', 'error'],
            'scheduling': ['schedule', 'resource', 'affinity', 'taint', 'toleration'],
            'volume': ['volume', 'mount', 'pvc', 'storage'],
            'image': ['image', 'pull', 'registry', 'repo'],
            'network': ['network', 'connect', 'route', 'ingress', 'service'],
            'resource': ['cpu', 'memory', 'limit', 'request', 'oom']
        }
        
        # Determine issue type based on finding
        issue_type = next((t for t, keywords in relation_keywords.items() 
                         if any(kw in finding_issue for kw in keywords)), None)
        
        if issue_type:
            # Check if event keywords match issue type
            if any(kw in event_reason or kw in event_message for kw in relation_keywords[issue_type]):
                return True
        
        return False
    
    def _create_findings_from_events(self, component: str, events: List[Dict]) -> None:
        """
        Create findings from important events.
        
        Args:
            component: Component identifier (Kind/Name)
            events: List of events for this component
        """
        # Filter for warning and error events
        important_events = [e for e in events if e.get('type', '') != 'Normal']
        
        if not important_events:
            return
            
        # Group by reason to avoid duplicate findings
        reason_groups = {}
        for event in important_events:
            reason = event.get('reason', 'Unknown')
            if reason not in reason_groups:
                reason_groups[reason] = []
            reason_groups[reason].append(event)
        
        # Create a finding for each reason group
        for reason, events_list in reason_groups.items():
            # Use the most recent event for the finding
            event = max(events_list, key=lambda e: e.get('lastTimestamp', ''))
            message = event.get('message', '')
            
            severity = "high" if reason in ['Failed', 'FailedCreate', 'FailedMount'] else "medium"
            
            self.add_finding(
                component=component,
                issue=f"Event warning: {reason}",
                severity=severity,
                evidence=f"Message: {message} (event count: {len(events_list)})",
                recommendation="Investigate the reported issue and take appropriate action"
            )
            
            # Log event details
            logger.info(f"Created finding from events for {component}, reason: {reason}, message: {message}")
    
    def _find_matching_pods(self, namespace: str, selector: Dict) -> List[Dict]:
        """
        Find pods matching a selector.
        
        Args:
            namespace: Namespace to search in
            selector: Label selector
            
        Returns:
            List of matching pods
        """
        pods = self.k8s_client.get_pods(namespace)
        matching_pods = []
        
        for pod in pods:
            labels = pod['metadata'].get('labels', {})
            if all(key in labels and labels[key] == value for key, value in selector.items()):
                matching_pods.append(pod)
                
        return matching_pods
    
    def _is_pod_healthy(self, pod: Dict) -> bool:
        """
        Check if a pod is healthy.
        
        Args:
            pod: Pod data
            
        Returns:
            True if healthy, False otherwise
        """
        # Check phase first
        phase = pod['status'].get('phase', '')
        if phase != 'Running':
            return False
            
        # Check if pod is ready
        conditions = pod['status'].get('conditions', [])
        ready_condition = next((c for c in conditions if c.get('type') == 'Ready'), None)
        if not ready_condition or ready_condition.get('status') != 'True':
            return False
            
        # Check container statuses
        container_statuses = pod['status'].get('containerStatuses', [])
        if not container_statuses:
            return False
            
        for status in container_statuses:
            if not status.get('ready', False):
                return False
                
            # Check for container in waiting state
            state = status.get('state', {})
            if 'waiting' in state:
                return False
                
            # Check for terminated state not due to completion
            if 'terminated' in state and state['terminated'].get('reason', '') != 'Completed':
                return False
                
        return True
    
    def _format_pod_status_evidence(self, status_groups: Dict[str, List[Dict]]) -> str:
        """
        Format pod status groups as evidence string.
        
        Args:
            status_groups: Dictionary of pod status groups
            
        Returns:
            Formatted evidence string
        """
        evidence = []
        
        for status, pods in status_groups.items():
            if status not in ['running', 'succeeded'] and pods:
                pod_names = [p['metadata']['name'] for p in pods[:5]]
                more_count = len(pods) - 5 if len(pods) > 5 else 0
                pod_list = ", ".join(pod_names)
                
                if more_count > 0:
                    pod_list += f" and {more_count} more"
                    
                evidence.append(f"{status.replace('_', ' ').title()}: {pod_list}")
                
        return "\n".join(evidence)
    
    def add_finding(self, component: str, issue: str, severity: str, evidence: str, recommendation: str) -> None:
        """
        Add a finding.
        
        Args:
            component: The component with the issue
            issue: Description of the issue
            severity: Severity level (critical, high, medium, low, info)
            evidence: Evidence supporting the finding
            recommendation: Recommended action to resolve the issue
        """
        finding = {
            'component': component,
            'issue': issue,
            'severity': severity,
            'evidence': evidence,
            'recommendation': recommendation,
            'timestamp': datetime.now().isoformat()
        }
        
        self.findings.append(finding)
        logger.info(f"Added finding: {component} - {issue} [{severity}]")
    
    def add_reasoning_step(self, observation: str, conclusion: str) -> None:
        """
        Add a reasoning step.
        
        Args:
            observation: What was observed in the data
            conclusion: What was concluded from the observation
        """
        step = {
            'observation': observation,
            'conclusion': conclusion,
            'timestamp': datetime.now().isoformat()
        }
        
        self.reasoning_steps.append(step)
        logger.info(f"Added reasoning step: {observation} -> {conclusion}")