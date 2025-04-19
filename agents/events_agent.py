from datetime import datetime, timedelta
from agents.base_agent import BaseAgent

class EventsAgent(BaseAgent):
    """
    Agent specialized in analyzing Kubernetes events.
    Focuses on cluster events, status changes, and control plane issues.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the events agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        super().__init__(k8s_client)
        
        # Define severity levels for different event types
        self.event_severity = {
            'Normal': 'info',
            'Warning': 'medium',
            'Error': 'high',
            'Critical': 'critical'
        }
        
        # Define event types to watch for
        self.critical_event_reasons = [
            'Failed', 'FailedCreate', 'FailedScheduling', 'FailedMount',
            'NodeNotReady', 'KubeletNotReady', 'FailedAttachVolume',
            'FailedDetachVolume', 'FreeDiskSpaceFailed', 'OutOfDisk',
            'MemoryPressure', 'DiskPressure', 'NetworkUnavailable',
            'Unhealthy', 'FailedSync', 'Evicted', 'BackOff', 'Error'
        ]
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Analyze events for the specified namespace.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the events analysis
        """
        self.reset()
        
        try:
            # Set the context if provided
            if context:
                self.k8s_client.set_context(context)
            
            # Get recent events for the namespace
            events = self.k8s_client.get_events(namespace)
            
            if not events:
                self.add_reasoning_step(
                    observation=f"No events found in namespace {namespace}",
                    conclusion="No event data to analyze"
                )
                return self.get_results()
            
            self.add_reasoning_step(
                observation=f"Found {len(events)} events in namespace {namespace}",
                conclusion="Beginning events analysis"
            )
            
            # Group events by their involved object
            object_events = self._group_events_by_object(events)
            
            # Analyze events for each object
            self._analyze_object_events(object_events)
            
            # Analyze scheduling issues
            self._analyze_scheduling_issues(events)
            
            # Analyze volume issues
            self._analyze_volume_issues(events)
            
            # Analyze frequent events
            self._analyze_frequent_events(events)
            
            # Analyze control plane issues
            self._analyze_control_plane_issues(events)
            
            # Analyze node issues
            self._analyze_node_issues(events)
            
            # Return the analysis results
            return self.get_results()
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during events analysis: {str(e)}",
                conclusion="Unable to complete events analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _group_events_by_object(self, events):
        """
        Group events by the objects they are associated with.
        
        Args:
            events: List of event data
        
        Returns:
            dict: Events grouped by object kind and name
        """
        object_events = {}
        
        for event in events:
            involved_object = event.get('involvedObject', {})
            kind = involved_object.get('kind', 'Unknown')
            name = involved_object.get('name', 'unknown')
            
            key = f"{kind}/{name}"
            
            if key not in object_events:
                object_events[key] = []
            
            object_events[key].append(event)
        
        self.add_reasoning_step(
            observation=f"Grouped events into {len(object_events)} unique objects",
            conclusion="Will analyze events by object type and name"
        )
        
        return object_events
    
    def _analyze_object_events(self, object_events):
        """
        Analyze events for each object.
        
        Args:
            object_events: Events grouped by object
        """
        # Look for objects with multiple warning/error events
        for obj_key, events in object_events.items():
            warning_events = [e for e in events if e.get('type', '') == 'Warning']
            
            if len(warning_events) >= 3:
                # Object has multiple warning events
                recent_warnings = sorted(warning_events, key=lambda e: e.get('lastTimestamp', ''), reverse=True)[:3]
                reasons = [e.get('reason', 'Unknown') for e in recent_warnings]
                messages = [e.get('message', '') for e in recent_warnings]
                
                reason_str = ", ".join(reasons)
                message_str = "\n".join([f"- {msg}" for msg in messages])
                
                self.add_finding(
                    component=obj_key,
                    issue=f"Multiple warning events detected for {obj_key}",
                    severity="high" if any(reason in self.critical_event_reasons for reason in reasons) else "medium",
                    evidence=f"Recent warnings ({reason_str}):\n{message_str}",
                    recommendation=f"Investigate the {obj_key} resource for configuration or operational issues"
                )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(warning_events)} warning events for {obj_key}",
                    conclusion=f"{obj_key} is experiencing recurring issues"
                )
    
    def _analyze_scheduling_issues(self, events):
        """
        Analyze events for scheduling issues.
        
        Args:
            events: List of event data
        """
        # Look for FailedScheduling events
        scheduling_events = [e for e in events if e.get('reason', '') == 'FailedScheduling']
        
        if scheduling_events:
            # Group by pod name
            pod_scheduling_issues = {}
            
            for event in scheduling_events:
                involved_object = event.get('involvedObject', {})
                pod_name = involved_object.get('name', 'unknown')
                
                if pod_name not in pod_scheduling_issues:
                    pod_scheduling_issues[pod_name] = []
                
                pod_scheduling_issues[pod_name].append(event)
            
            # Analyze each pod's scheduling issues
            for pod_name, pod_events in pod_scheduling_issues.items():
                latest_event = max(pod_events, key=lambda e: e.get('lastTimestamp', ''))
                message = latest_event.get('message', '')
                
                # Determine the likely cause
                cause = "unknown"
                recommendation = "Check node resources and pod resource requirements"
                
                if "Insufficient cpu" in message:
                    cause = "insufficient CPU"
                    recommendation = "Increase CPU capacity in your cluster or reduce CPU requests"
                elif "Insufficient memory" in message:
                    cause = "insufficient memory"
                    recommendation = "Increase memory capacity in your cluster or reduce memory requests"
                elif "node(s) had taint" in message:
                    cause = "node taints"
                    recommendation = "Add appropriate tolerations to the pod or remove taints from nodes"
                elif "node(s) didn't match node selector" in message:
                    cause = "node selector mismatch"
                    recommendation = "Update the pod's node selector or label your nodes correctly"
                elif "persistentvolumeclaim" in message.lower() and "pending" in message.lower():
                    cause = "pending PVC"
                    recommendation = "Check the PVC status and ensure storage is available"
                
                self.add_finding(
                    component=f"Pod/{pod_name}",
                    issue=f"Pod scheduling failed due to {cause}",
                    severity="high",
                    evidence=f"Message: {message}",
                    recommendation=recommendation
                )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(pod_events)} scheduling failures for pod {pod_name}",
                    conclusion=f"Pod {pod_name} cannot be scheduled due to {cause}"
                )
    
    def _analyze_volume_issues(self, events):
        """
        Analyze events for volume-related issues.
        
        Args:
            events: List of event data
        """
        # Look for volume-related events
        volume_events = [
            e for e in events if any(reason in e.get('reason', '') 
                                    for reason in ['FailedMount', 'FailedAttachVolume', 'FailedDetachVolume'])
        ]
        
        if volume_events:
            # Group by involved object
            object_volume_issues = {}
            
            for event in volume_events:
                involved_object = event.get('involvedObject', {})
                obj_key = f"{involved_object.get('kind', 'Unknown')}/{involved_object.get('name', 'unknown')}"
                
                if obj_key not in object_volume_issues:
                    object_volume_issues[obj_key] = []
                
                object_volume_issues[obj_key].append(event)
            
            # Analyze each object's volume issues
            for obj_key, obj_events in object_volume_issues.items():
                latest_event = max(obj_events, key=lambda e: e.get('lastTimestamp', ''))
                reason = latest_event.get('reason', '')
                message = latest_event.get('message', '')
                
                # Determine the likely cause and recommendation
                cause = "unknown issue"
                recommendation = "Check the volume configuration and storage system"
                
                if "timeout" in message.lower():
                    cause = "mounting timeout"
                    recommendation = "Check if storage system is responsive and resources are available"
                elif "no such file" in message.lower():
                    cause = "path doesn't exist"
                    recommendation = "Verify the volume path exists in the source"
                elif "permission denied" in message.lower():
                    cause = "permission issue"
                    recommendation = "Check volume permissions and pod security context"
                elif "not found" in message.lower() and "pvc" in message.lower():
                    cause = "PVC not found"
                    recommendation = "Ensure the PVC exists and is in the correct namespace"
                
                self.add_finding(
                    component=obj_key,
                    issue=f"Volume operation failed due to {cause}",
                    severity="high",
                    evidence=f"Reason: {reason}, Message: {message}",
                    recommendation=recommendation
                )
                
                self.add_reasoning_step(
                    observation=f"Detected {len(obj_events)} volume issues for {obj_key}",
                    conclusion=f"{obj_key} is experiencing volume issues: {cause}"
                )
    
    def _analyze_frequent_events(self, events):
        """
        Analyze events for patterns of frequent repetition.
        
        Args:
            events: List of event data
        """
        # Look for events with high count
        high_count_events = [e for e in events if e.get('count', 1) > 5]
        
        if high_count_events:
            # Sort by count descending
            high_count_events.sort(key=lambda e: e.get('count', 1), reverse=True)
            
            for event in high_count_events[:5]:  # Look at the top 5 most frequent events
                count = event.get('count', 0)
                involved_object = event.get('involvedObject', {})
                kind = involved_object.get('kind', 'Unknown')
                name = involved_object.get('name', 'unknown')
                reason = event.get('reason', 'Unknown')
                message = event.get('message', '')
                event_type = event.get('type', 'Normal')
                
                # Only report frequent warning events
                if event_type == 'Warning':
                    self.add_finding(
                        component=f"{kind}/{name}",
                        issue=f"Frequent {reason} events detected ({count} occurrences)",
                        severity="high" if count > 20 else "medium",
                        evidence=f"Message: {message}",
                        recommendation=f"Investigate the root cause of these recurring events on {kind} {name}"
                    )
                    
                    self.add_reasoning_step(
                        observation=f"Detected {count} occurrences of {reason} events for {kind}/{name}",
                        conclusion="Recurring events indicate a persistent issue that needs attention"
                    )
    
    def _analyze_control_plane_issues(self, events):
        """
        Analyze events for control plane issues.
        
        Args:
            events: List of event data
        """
        # Look for events related to control plane components
        control_plane_events = [
            e for e in events if any(component in e.get('source', {}).get('component', '')
                                    for component in ['kube-apiserver', 'kube-controller-manager', 'kube-scheduler', 'etcd'])
        ]
        
        if control_plane_events:
            # Group by component
            component_issues = {}
            
            for event in control_plane_events:
                component = event.get('source', {}).get('component', 'unknown')
                
                if component not in component_issues:
                    component_issues[component] = []
                
                component_issues[component].append(event)
            
            # Analyze issues for each component
            for component, comp_events in component_issues.items():
                warning_events = [e for e in comp_events if e.get('type', '') == 'Warning']
                
                if warning_events:
                    latest_warning = max(warning_events, key=lambda e: e.get('lastTimestamp', ''))
                    reason = latest_warning.get('reason', 'Unknown')
                    message = latest_warning.get('message', '')
                    
                    self.add_finding(
                        component=f"Control Plane/{component}",
                        issue=f"Control plane component {component} reporting warnings",
                        severity="critical",
                        evidence=f"Reason: {reason}, Message: {message}",
                        recommendation=f"Investigate health of {component} in your Kubernetes control plane"
                    )
                    
                    self.add_reasoning_step(
                        observation=f"Detected {len(warning_events)} warning events from {component}",
                        conclusion=f"Control plane component {component} may be experiencing issues"
                    )
    
    def _analyze_node_issues(self, events):
        """
        Analyze events for node-related issues.
        
        Args:
            events: List of event data
        """
        # Look for events related to node problems
        node_events = [
            e for e in events 
            if e.get('involvedObject', {}).get('kind', '') == 'Node' or
               any(condition in e.get('reason', '') 
                  for condition in ['NodeNotReady', 'KubeletNotReady', 'MemoryPressure', 'DiskPressure', 'NetworkUnavailable'])
        ]
        
        if node_events:
            # Group by node
            node_issues = {}
            
            for event in node_events:
                involved_object = event.get('involvedObject', {})
                if involved_object.get('kind', '') == 'Node':
                    node_name = involved_object.get('name', 'unknown')
                else:
                    # For events not directly on nodes but related to node conditions
                    node_name = event.get('source', {}).get('host', 'unknown')
                
                if node_name not in node_issues:
                    node_issues[node_name] = []
                
                node_issues[node_name].append(event)
            
            # Analyze issues for each node
            for node_name, node_events in node_issues.items():
                warning_events = [e for e in node_events if e.get('type', '') == 'Warning']
                
                if warning_events:
                    latest_warning = max(warning_events, key=lambda e: e.get('lastTimestamp', ''))
                    reason = latest_warning.get('reason', 'Unknown')
                    message = latest_warning.get('message', '')
                    
                    # Determine issue type and recommendation
                    issue_type = "unknown issue"
                    recommendation = "Investigate the node's status and logs"
                    
                    if 'NotReady' in reason:
                        issue_type = "node not ready"
                        recommendation = "Check kubelet status, node connectivity, and system logs on the node"
                    elif 'MemoryPressure' in reason:
                        issue_type = "memory pressure"
                        recommendation = "Free up memory on the node or add more memory resources"
                    elif 'DiskPressure' in reason:
                        issue_type = "disk pressure"
                        recommendation = "Free up disk space on the node or expand storage"
                    elif 'NetworkUnavailable' in reason:
                        issue_type = "network unavailable"
                        recommendation = "Check network configuration, CNI plugins, and network connectivity"
                    
                    self.add_finding(
                        component=f"Node/{node_name}",
                        issue=f"Node experiencing {issue_type}",
                        severity="critical",
                        evidence=f"Reason: {reason}, Message: {message}",
                        recommendation=recommendation
                    )
                    
                    self.add_reasoning_step(
                        observation=f"Detected {len(warning_events)} warning events for node {node_name}",
                        conclusion=f"Node {node_name} is experiencing {issue_type}"
                    )
