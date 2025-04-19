import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from utils.kubernetes_client import KubernetesClient

class TracesAgent:
    """
    Agent responsible for analyzing distributed traces across services.
    Identifies latency bottlenecks, errors in request flows, and service dependencies.
    """
    
    def __init__(self, k8s_client: KubernetesClient):
        """
        Initialize the traces agent with a Kubernetes client.
        
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
        Analyze traces for the specified namespace.
        
        Args:
            namespace: Kubernetes namespace to analyze
            start_time: Start time for trace collection
            end_time: End time for trace collection
            
        Returns:
            Dict containing traces analysis results
        """
        # Default times if not provided
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now()
        
        # Collect traces
        traces = self._collect_traces(namespace, start_time, end_time)
        
        # Generate trace map
        trace_map = self._generate_trace_map(traces)
        
        # Identify latency issues
        latency_issues = self._identify_latency_issues(traces)
        
        # Identify error paths
        error_paths = self._identify_error_paths(traces)
        
        # Prepare results
        results = {
            'trace_map': trace_map,
            'latency_issues': latency_issues,
            'error_paths': error_paths,
            'trace_stats': self._get_trace_stats(traces)
        }
        
        return results
    
    def _collect_traces(
        self, 
        namespace: str, 
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Collect traces from services in the namespace.
        
        Args:
            namespace: Kubernetes namespace to collect traces from
            start_time: Start time for trace collection
            end_time: End time for trace collection
            
        Returns:
            List of traces
        """
        # In a real implementation, this would query traces from a tracing system (Jaeger, Zipkin, etc.)
        # For this example, we'll simulate trace collection
        
        # Get services in the namespace
        services = self.k8s_client.get_services(namespace)
        
        if not services:
            return []
        
        # Simulate traces
        traces = []
        
        # Create a service dependency graph based on service names
        service_names = [service['name'] for service in services]
        
        # Simplified dependency representation (service -> dependencies)
        dependencies = {}
        
        # Create random dependencies between services
        for service in service_names:
            # Each service might depend on 0-3 other services
            num_deps = min(len(service_names) - 1, np.random.randint(0, 4))
            potential_deps = [s for s in service_names if s != service]
            
            if potential_deps and num_deps > 0:
                dependencies[service] = np.random.choice(
                    potential_deps, 
                    size=min(num_deps, len(potential_deps)), 
                    replace=False
                ).tolist()
            else:
                dependencies[service] = []
        
        # Generate entry points (services that receive external requests)
        entry_points = np.random.choice(
            service_names, 
            size=min(3, len(service_names)), 
            replace=False
        ).tolist()
        
        # Generate trace timestamps
        time_diff = (end_time - start_time).total_seconds()
        num_traces = max(10, min(100, int(time_diff / 60)))  # 1 trace per minute, capped at 100
        trace_timestamps = [
            start_time + timedelta(seconds=np.random.uniform(0, time_diff)) 
            for _ in range(num_traces)
        ]
        trace_timestamps.sort()
        
        # HTTP methods and paths
        http_methods = ['GET', 'POST', 'PUT', 'DELETE']
        http_paths = [
            '/api/users', 
            '/api/products', 
            '/api/orders', 
            '/api/payments',
            '/health',
            '/metrics',
            '/status'
        ]
        
        # HTTP status codes
        status_codes = [200, 201, 400, 401, 403, 404, 500, 503]
        status_weights = [0.7, 0.1, 0.05, 0.03, 0.02, 0.05, 0.03, 0.02]  # Probabilities
        
        # Generate traces
        for trace_idx, timestamp in enumerate(trace_timestamps):
            trace_id = f"trace-{trace_idx+1}"
            
            # Choose an entry point
            entry_service = np.random.choice(entry_points)
            
            # Choose HTTP method and path
            http_method = np.random.choice(http_methods)
            http_path = np.random.choice(http_paths)
            
            # Generate spans for this trace
            spans = []
            
            # Process queue of services to trace
            service_queue = [(entry_service, 0, None)]  # (service, depth, parent_id)
            span_id = 0
            
            while service_queue:
                service, depth, parent_id = service_queue.pop(0)
                span_id += 1
                
                # Determine span duration (deeper spans tend to be shorter)
                base_duration = max(5, 100 / (depth + 1))
                duration = max(1, np.random.normal(base_duration, base_duration / 3))
                
                # Add some longer operations randomly
                if np.random.random() < 0.1:  # 10% chance of a slow operation
                    duration *= np.random.uniform(2, 5)
                
                # Determine status code
                status_code = np.random.choice(status_codes, p=status_weights)
                
                # Create span
                span = {
                    'trace_id': trace_id,
                    'span_id': f"span-{trace_id}-{span_id}",
                    'parent_id': parent_id,
                    'service': service,
                    'operation': f"{http_method} {http_path}",
                    'start_time': timestamp + timedelta(milliseconds=depth * 10),
                    'duration_ms': duration,
                    'status_code': status_code,
                    'error': status_code >= 400
                }
                
                spans.append(span)
                
                # Process dependencies if status code is successful
                if status_code < 400 and service in dependencies:
                    for dep_service in dependencies[service]:
                        service_queue.append((dep_service, depth + 1, span['span_id']))
            
            traces.append({
                'trace_id': trace_id,
                'timestamp': timestamp,
                'spans': spans
            })
        
        return traces
    
    def _generate_trace_map(self, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a service dependency map from traces.
        
        Args:
            traces: List of traces
            
        Returns:
            Dict representing the service trace map
        """
        if not traces:
            return {
                'nodes': [],
                'edges': []
            }
        
        # Extract services (nodes)
        services = set()
        for trace in traces:
            for span in trace['spans']:
                services.add(span['service'])
        
        # Create nodes
        nodes = [{'id': service, 'label': service} for service in services]
        
        # Extract service dependencies (edges)
        edges = []
        edge_stats = {}  # (source, target) -> {count, errors, latency}
        
        for trace in traces:
            for span in trace['spans']:
                if span['parent_id']:
                    # Find parent span
                    parent_span = next(
                        (s for s in trace['spans'] if s['span_id'] == span['parent_id']),
                        None
                    )
                    
                    if parent_span:
                        source = parent_span['service']
                        target = span['service']
                        
                        edge_key = (source, target)
                        
                        if edge_key not in edge_stats:
                            edge_stats[edge_key] = {
                                'count': 0,
                                'errors': 0,
                                'latency_sum': 0
                            }
                        
                        edge_stats[edge_key]['count'] += 1
                        
                        if span['error']:
                            edge_stats[edge_key]['errors'] += 1
                        
                        edge_stats[edge_key]['latency_sum'] += span['duration_ms']
        
        # Create edges with statistics
        for (source, target), stats in edge_stats.items():
            avg_latency = stats['latency_sum'] / stats['count'] if stats['count'] > 0 else 0
            error_rate = (stats['errors'] / stats['count']) * 100 if stats['count'] > 0 else 0
            
            edges.append({
                'source': source,
                'target': target,
                'count': stats['count'],
                'avg_latency': round(avg_latency, 2),
                'error_rate': round(error_rate, 2),
                'label': f"{round(avg_latency, 0)}ms ({stats['count']} calls)"
            })
        
        # Sort by count (descending)
        edges.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'nodes': nodes,
            'edges': edges
        }
    
    def _identify_latency_issues(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify latency issues from traces.
        
        Args:
            traces: List of traces
            
        Returns:
            List of identified latency issues
        """
        if not traces:
            return []
        
        # Collect span latencies by service and operation
        latencies = {}  # service -> operation -> latencies
        
        for trace in traces:
            for span in trace['spans']:
                service = span['service']
                operation = span['operation']
                
                if service not in latencies:
                    latencies[service] = {}
                
                if operation not in latencies[service]:
                    latencies[service][operation] = []
                
                latencies[service][operation].append(span['duration_ms'])
        
        # Identify latency outliers
        issues = []
        
        for service, operations in latencies.items():
            for operation, durations in operations.items():
                # Calculate statistics
                avg_latency = np.mean(durations)
                p95_latency = np.percentile(durations, 95)
                max_latency = np.max(durations)
                
                # Check for slow operations (p95 > 500ms)
                if p95_latency > 500:
                    issues.append({
                        'service': service,
                        'operation': operation,
                        'avg_latency': round(avg_latency, 2),
                        'p95_latency': round(p95_latency, 2),
                        'max_latency': round(max_latency, 2),
                        'severity': 'High' if p95_latency > 1000 else 'Medium',
                        'description': f"Slow operation detected: p95 latency of {round(p95_latency, 2)}ms"
                    })
                
                # Check for high variance
                if len(durations) > 5:
                    std_dev = np.std(durations)
                    cv = std_dev / avg_latency if avg_latency > 0 else 0
                    
                    if cv > 1.0:  # Coefficient of variation > 1.0 indicates high variance
                        issues.append({
                            'service': service,
                            'operation': operation,
                            'avg_latency': round(avg_latency, 2),
                            'std_dev': round(std_dev, 2),
                            'cv': round(cv, 2),
                            'severity': 'Medium',
                            'description': f"High latency variance detected: coefficient of variation {round(cv, 2)}"
                        })
        
        # Sort by severity (High first) and then by p95 latency
        issues.sort(key=lambda x: (0 if x['severity'] == 'High' else 1, -x.get('p95_latency', 0)))
        
        return issues
    
    def _identify_error_paths(self, traces: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify error paths in traces.
        
        Args:
            traces: List of traces
            
        Returns:
            List of identified error paths
        """
        if not traces:
            return []
        
        # Collect error rates by service and operation
        error_stats = {}  # service -> operation -> {count, errors}
        
        for trace in traces:
            for span in trace['spans']:
                service = span['service']
                operation = span['operation']
                
                if service not in error_stats:
                    error_stats[service] = {}
                
                if operation not in error_stats[service]:
                    error_stats[service][operation] = {'count': 0, 'errors': 0}
                
                error_stats[service][operation]['count'] += 1
                
                if span['error']:
                    error_stats[service][operation]['errors'] += 1
        
        # Identify operations with high error rates
        error_paths = []
        
        for service, operations in error_stats.items():
            for operation, stats in operations.items():
                if stats['count'] >= 5:  # Require at least 5 occurrences
                    error_rate = (stats['errors'] / stats['count']) * 100
                    
                    if error_rate >= 5:  # 5% or higher error rate
                        error_paths.append({
                            'service': service,
                            'operation': operation,
                            'error_count': stats['errors'],
                            'total_count': stats['count'],
                            'error_rate': round(error_rate, 2),
                            'severity': 'High' if error_rate >= 20 else 'Medium',
                            'description': f"High error rate ({round(error_rate, 2)}%) for operation"
                        })
        
        # Sort by error rate (descending)
        error_paths.sort(key=lambda x: x['error_rate'], reverse=True)
        
        return error_paths
    
    def _get_trace_stats(self, traces: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate statistics about the traces.
        
        Args:
            traces: List of traces
            
        Returns:
            Dict containing trace statistics
        """
        if not traces:
            return {
                'total_traces': 0,
                'total_spans': 0,
                'avg_spans_per_trace': 0,
                'error_rate': 0
            }
        
        total_traces = len(traces)
        total_spans = sum(len(trace['spans']) for trace in traces)
        avg_spans_per_trace = total_spans / total_traces if total_traces > 0 else 0
        
        # Count traces with errors
        error_traces = sum(
            1 for trace in traces 
            if any(span['error'] for span in trace['spans'])
        )
        error_rate = (error_traces / total_traces) * 100 if total_traces > 0 else 0
        
        # Count spans by service
        services = {}
        for trace in traces:
            for span in trace['spans']:
                service = span['service']
                
                if service not in services:
                    services[service] = {'count': 0, 'errors': 0, 'latency_sum': 0}
                
                services[service]['count'] += 1
                
                if span['error']:
                    services[service]['errors'] += 1
                
                services[service]['latency_sum'] += span['duration_ms']
        
        # Calculate service stats
        service_stats = []
        for service, stats in services.items():
            avg_latency = stats['latency_sum'] / stats['count'] if stats['count'] > 0 else 0
            error_rate = (stats['errors'] / stats['count']) * 100 if stats['count'] > 0 else 0
            
            service_stats.append({
                'service': service,
                'span_count': stats['count'],
                'avg_latency': round(avg_latency, 2),
                'error_rate': round(error_rate, 2)
            })
        
        # Sort by span count (descending)
        service_stats.sort(key=lambda x: x['span_count'], reverse=True)
        
        return {
            'total_traces': total_traces,
            'total_spans': total_spans,
            'avg_spans_per_trace': round(avg_spans_per_trace, 2),
            'error_rate': round(error_rate, 2),
            'services': service_stats
        }
