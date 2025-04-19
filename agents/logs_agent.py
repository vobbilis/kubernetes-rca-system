import re
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import Counter

from utils.kubernetes_client import KubernetesClient

class LogsAgent:
    """
    Agent responsible for analyzing application logs from Kubernetes pods.
    Identifies error patterns, exceptions, and trends in log data.
    """
    
    def __init__(self, k8s_client: KubernetesClient):
        """
        Initialize the logs agent with a Kubernetes client.
        
        Args:
            k8s_client: An initialized Kubernetes client for interacting with the cluster
        """
        self.k8s_client = k8s_client
        
        # Common error patterns to search for
        self.error_patterns = [
            r'error|exception|failed|failure|timeout|refused|unable to|cannot|denied',
            r'NullPointerException|IndexOutOfBoundsException|IllegalStateException',
            r'segmentation fault|core dumped|killed|OOMKilled',
            r'warning|[wW]arn',
            r'HTTP/\d+\.\d+"\s+[45]\d\d'  # HTTP 4xx and 5xx status codes
        ]
    
    def analyze(
        self, 
        namespace: str, 
        resource_type: Optional[str] = None, 
        resource_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Analyze logs for the specified resources.
        
        Args:
            namespace: Kubernetes namespace to analyze
            resource_type: Type of resource to analyze (pod, deployment, etc.)
            resource_name: Name of the specific resource to analyze
            start_time: Start time for log collection
            end_time: End time for log collection
            
        Returns:
            Dict containing logs analysis results
        """
        # Default times if not provided
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now()
        
        # Collect logs
        logs = self._collect_logs(namespace, resource_type, resource_name, start_time, end_time)
        
        # Extract error patterns
        error_patterns = self._extract_error_patterns(logs)
        
        # Create log timeline
        timeline = self._create_timeline(logs)
        
        # Prepare results
        results = {
            'error_patterns': error_patterns,
            'timeline': timeline,
            'log_stats': self._get_log_stats(logs)
        }
        
        return results
    
    def _collect_logs(
        self, 
        namespace: str, 
        resource_type: Optional[str], 
        resource_name: Optional[str],
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Collect logs from Kubernetes resources.
        
        Args:
            namespace: Kubernetes namespace to analyze
            resource_type: Type of resource to collect logs for
            resource_name: Name of the specific resource to collect logs for
            start_time: Start time for log collection
            end_time: End time for log collection
            
        Returns:
            List of log entries
        """
        # In a real implementation, this would query logs using kubectl or the K8s API
        # For this example, we'll simulate log collection
        
        # Determine target pods
        if resource_type == 'pod' and resource_name:
            target_pods = [resource_name]
        elif resource_type == 'deployment' and resource_name:
            # For a deployment, we need to get all its pods
            pods = self.k8s_client.get_pods_for_deployment(namespace, resource_name)
            target_pods = [pod['name'] for pod in pods]
        else:
            # Get all pods in the namespace
            pods = self.k8s_client.get_pods(namespace)
            target_pods = [pod['name'] for pod in pods]
        
        # Simulate log entries
        log_entries = []
        
        # Common log severity levels
        severities = ['INFO', 'DEBUG', 'WARN', 'ERROR', 'CRITICAL']
        severity_weights = [0.7, 0.15, 0.1, 0.04, 0.01]  # Probabilities for each severity
        
        # Common log messages
        info_messages = [
            "Application started successfully",
            "Processing request",
            "Request completed successfully",
            "Connection established",
            "User authenticated",
            "Data loaded successfully",
            "Cache refreshed",
            "Scheduled task executed",
            "Configuration loaded"
        ]
        
        debug_messages = [
            "Debug: Processing item",
            "Debug: Variable value is",
            "Debug: Method called with parameters",
            "Debug: Query executed in",
            "Debug: Cache hit for key"
        ]
        
        warn_messages = [
            "Warning: Slow query detected",
            "Warning: High memory usage",
            "Warning: Deprecated API call",
            "Warning: Connection pool running low",
            "Warning: Request rate high",
            "Warning: Cache miss rate increasing"
        ]
        
        error_messages = [
            "Error: Failed to connect to service",
            "Error: Database query failed",
            "Error: Timeout waiting for response",
            "Error: Invalid input data",
            "Error: Authentication failed",
            "Error: File not found",
            "Error: Out of memory",
            "Error: Exception in thread",
            "Error: NullPointerException",
            "Error: Connection refused",
            "Error: HTTP 500 response from API"
        ]
        
        critical_messages = [
            "CRITICAL: System is out of resources",
            "CRITICAL: Database connection lost",
            "CRITICAL: Service terminated unexpectedly",
            "CRITICAL: Data corruption detected",
            "CRITICAL: Unable to recover from exception"
        ]
        
        # Generate time points for logs
        time_diff = (end_time - start_time).total_seconds()
        
        # Generate logs for each pod
        for pod_name in target_pods:
            # Determine number of log entries based on time range
            num_entries = int(time_diff / 10)  # Approx 1 log entry per 10 seconds
            
            # Add some randomness
            num_entries = max(10, int(num_entries * np.random.uniform(0.8, 1.2)))
            
            # Generate timestamps
            timestamps = [start_time + timedelta(seconds=np.random.uniform(0, time_diff)) for _ in range(num_entries)]
            timestamps.sort()
            
            # Generate log entries
            for timestamp in timestamps:
                # Select severity based on weights
                severity = np.random.choice(severities, p=severity_weights)
                
                # Select appropriate message based on severity
                if severity == 'INFO':
                    message = np.random.choice(info_messages)
                elif severity == 'DEBUG':
                    message = np.random.choice(debug_messages)
                elif severity == 'WARN':
                    message = np.random.choice(warn_messages)
                elif severity == 'ERROR':
                    message = np.random.choice(error_messages)
                else:  # CRITICAL
                    message = np.random.choice(critical_messages)
                
                # Add some randomness to messages
                if np.random.random() < 0.3:  # 30% chance to add details
                    if severity in ['INFO', 'DEBUG']:
                        message += f" (id={np.random.randint(1000, 9999)})"
                    elif severity in ['WARN', 'ERROR', 'CRITICAL']:
                        message += f": {np.random.choice(['timeout after 30s', 'received null response', 'unexpected status code', 'connection reset'])}"
                
                log_entries.append({
                    'pod': pod_name,
                    'timestamp': timestamp,
                    'severity': severity,
                    'message': message
                })
        
        # Add some specific error patterns to make analysis interesting
        if len(log_entries) > 10:
            # Simulate a recurring error pattern
            error_pod = np.random.choice(target_pods)
            error_times = [
                start_time + timedelta(seconds=np.random.uniform(0, time_diff/3)),
                start_time + timedelta(seconds=np.random.uniform(time_diff/3, 2*time_diff/3)),
                start_time + timedelta(seconds=np.random.uniform(2*time_diff/3, time_diff))
            ]
            
            for error_time in error_times:
                log_entries.append({
                    'pod': error_pod,
                    'timestamp': error_time,
                    'severity': 'ERROR',
                    'message': "Error: Connection refused to database. Retrying in 5s..."
                })
            
            # Simulate an exception
            exception_pod = np.random.choice(target_pods)
            exception_time = start_time + timedelta(seconds=np.random.uniform(time_diff/2, time_diff))
            
            log_entries.append({
                'pod': exception_pod,
                'timestamp': exception_time,
                'severity': 'ERROR',
                'message': "Error: Exception in thread \"main\" java.lang.NullPointerException at com.example.MyService.processRequest(MyService.java:42)"
            })
            
            # Simulate an OOM event
            if np.random.random() < 0.3:  # 30% chance to add OOM
                oom_pod = np.random.choice(target_pods)
                oom_time = start_time + timedelta(seconds=np.random.uniform(time_diff*0.7, time_diff))
                
                log_entries.append({
                    'pod': oom_pod,
                    'timestamp': oom_time,
                    'severity': 'CRITICAL',
                    'message': "CRITICAL: Container killed due to OOMKilled"
                })
        
        # Sort log entries by timestamp
        log_entries.sort(key=lambda x: x['timestamp'])
        
        return log_entries
    
    def _extract_error_patterns(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract error patterns from logs.
        
        Args:
            logs: List of log entries
            
        Returns:
            List of identified error patterns
        """
        # Filter logs for errors and warnings
        error_logs = [log for log in logs if log['severity'] in ['ERROR', 'CRITICAL', 'WARN']]
        
        if not error_logs:
            return []
        
        # Extract messages
        messages = [log['message'] for log in error_logs]
        
        # Match common error patterns
        pattern_matches = []
        
        for pattern in self.error_patterns:
            matches = []
            
            for msg in messages:
                if re.search(pattern, msg, re.IGNORECASE):
                    matches.append(msg)
            
            if matches:
                pattern_matches.append({
                    'pattern': pattern,
                    'count': len(matches),
                    'examples': matches[:3]  # Include up to 3 examples
                })
        
        # Look for repeated exact error messages
        error_counter = Counter(messages)
        repeated_errors = [{'pattern': msg, 'count': count, 'examples': [msg]} 
                          for msg, count in error_counter.items() 
                          if count > 1]
        
        # Combine patterns
        all_patterns = pattern_matches + repeated_errors
        
        # Sort by count (descending)
        all_patterns.sort(key=lambda x: x['count'], reverse=True)
        
        return all_patterns
    
    def _create_timeline(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create a timeline of log events.
        
        Args:
            logs: List of log entries
            
        Returns:
            List of timeline events
        """
        timeline = []
        
        # Group logs by time window
        time_windows = {}
        window_size = timedelta(minutes=5)
        
        for log in logs:
            # Round timestamp to nearest 5-minute window
            window_start = log['timestamp'].replace(
                minute=(log['timestamp'].minute // 5) * 5,
                second=0,
                microsecond=0
            )
            
            window_key = window_start.isoformat()
            
            if window_key not in time_windows:
                time_windows[window_key] = {
                    'timestamp': window_start,
                    'INFO': 0, 'DEBUG': 0, 'WARN': 0, 'ERROR': 0, 'CRITICAL': 0,
                    'messages': []
                }
            
            # Count by severity
            time_windows[window_key][log['severity']] += 1
            
            # Store important messages
            if log['severity'] in ['ERROR', 'CRITICAL'] and len(time_windows[window_key]['messages']) < 5:
                time_windows[window_key]['messages'].append({
                    'severity': log['severity'],
                    'pod': log['pod'],
                    'message': log['message']
                })
        
        # Convert to timeline format
        for window_key, window_data in time_windows.items():
            severity = 'normal'
            
            # Determine severity based on log counts
            if window_data['CRITICAL'] > 0:
                severity = 'critical'
            elif window_data['ERROR'] > 3:
                severity = 'error'
            elif window_data['ERROR'] > 0 or window_data['WARN'] > 5:
                severity = 'warning'
            
            message = ''
            if window_data['messages']:
                message = window_data['messages'][0]['message']
            
            # Total count
            count = sum([window_data[s] for s in ['INFO', 'DEBUG', 'WARN', 'ERROR', 'CRITICAL']])
            
            timeline.append({
                'timestamp': window_data['timestamp'].isoformat(),
                'severity': severity,
                'count': count,
                'error_count': window_data['ERROR'] + window_data['CRITICAL'],
                'warn_count': window_data['WARN'],
                'info_count': window_data['INFO'] + window_data['DEBUG'],
                'message': message
            })
        
        return timeline
    
    def _get_log_stats(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistics about the logs.
        
        Args:
            logs: List of log entries
            
        Returns:
            Dict containing log statistics
        """
        if not logs:
            return {
                'total_entries': 0,
                'error_rate': 0,
                'pods': []
            }
        
        # Count by severity
        severity_counts = Counter([log['severity'] for log in logs])
        
        # Count by pod
        pod_counts = Counter([log['pod'] for log in logs])
        
        # Calculate error rate
        error_count = severity_counts.get('ERROR', 0) + severity_counts.get('CRITICAL', 0)
        total_count = len(logs)
        error_rate = (error_count / total_count) * 100 if total_count > 0 else 0
        
        # Get pods with highest error rates
        pod_error_counts = {}
        for log in logs:
            if log['severity'] in ['ERROR', 'CRITICAL']:
                pod_error_counts[log['pod']] = pod_error_counts.get(log['pod'], 0) + 1
        
        pod_error_rates = [
            {
                'pod': pod,
                'total_logs': pod_counts[pod],
                'error_logs': pod_error_counts.get(pod, 0),
                'error_rate': (pod_error_counts.get(pod, 0) / pod_counts[pod]) * 100 if pod_counts[pod] > 0 else 0
            }
            for pod in pod_counts
        ]
        
        # Sort by error rate (descending)
        pod_error_rates.sort(key=lambda x: x['error_rate'], reverse=True)
        
        return {
            'total_entries': total_count,
            'by_severity': {severity: count for severity, count in severity_counts.items()},
            'error_rate': error_rate,
            'pods': pod_error_rates
        }
