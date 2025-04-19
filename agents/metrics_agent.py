import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from utils.kubernetes_client import KubernetesClient

class MetricsAgent:
    """
    Agent responsible for analyzing resource metrics from Kubernetes pods and nodes.
    Identifies anomalies and performance issues based on CPU, memory, and network usage.
    """
    
    def __init__(self, k8s_client: KubernetesClient):
        """
        Initialize the metrics agent with a Kubernetes client.
        
        Args:
            k8s_client: An initialized Kubernetes client for interacting with the cluster
        """
        self.k8s_client = k8s_client
    
    def analyze(
        self, 
        namespace: str, 
        resource_type: Optional[str] = None, 
        resource_name: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Analyze metrics for the specified resources.
        
        Args:
            namespace: Kubernetes namespace to analyze
            resource_type: Type of resource to analyze (pod, deployment, etc.)
            resource_name: Name of the specific resource to analyze
            start_time: Start time for metrics collection
            end_time: End time for metrics collection
            
        Returns:
            Dict containing metrics analysis results
        """
        # Default times if not provided
        if not start_time:
            start_time = datetime.now() - timedelta(hours=1)
        if not end_time:
            end_time = datetime.now()
        
        # Collect metrics
        metrics = self._collect_metrics(namespace, resource_type, resource_name, start_time, end_time)
        
        # Analyze resource usage
        resource_usage = self._analyze_resource_usage(metrics)
        
        # Detect anomalies
        anomalies = self._detect_anomalies(metrics)
        
        # Prepare results
        results = {
            'resource_usage': resource_usage,
            'anomalies': anomalies,
            'raw_metrics': self._format_raw_metrics(metrics)
        }
        
        return results
    
    def _collect_metrics(
        self, 
        namespace: str, 
        resource_type: Optional[str], 
        resource_name: Optional[str],
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Collect metrics from the Kubernetes metrics API.
        
        Args:
            namespace: Kubernetes namespace to analyze
            resource_type: Type of resource to collect metrics for
            resource_name: Name of the specific resource to collect metrics for
            start_time: Start time for metrics collection
            end_time: End time for metrics collection
            
        Returns:
            Dict containing collected metrics
        """
        # In a real implementation, this would query the Kubernetes Metrics API
        # For this example, we'll simulate metric collection based on resource type
        
        metrics = {
            'cpu': {},
            'memory': {},
            'network': {}
        }
        
        # Determine target resources
        if resource_type == 'pod' and resource_name:
            targets = [{'name': resource_name, 'type': 'pod'}]
        elif resource_type == 'deployment' and resource_name:
            # For a deployment, we need to get all its pods
            pods = self.k8s_client.get_pods_for_deployment(namespace, resource_name)
            targets = [{'name': pod['name'], 'type': 'pod'} for pod in pods]
        else:
            # Get all pods in the namespace
            pods = self.k8s_client.get_pods(namespace)
            targets = [{'name': pod['name'], 'type': 'pod'} for pod in pods]
        
        # Generate time points for metrics
        time_range = (end_time - start_time).total_seconds() / 60  # minutes
        time_points = [start_time + timedelta(minutes=i) for i in range(int(time_range) + 1)]
        
        # Collect metrics for each target
        for target in targets:
            # CPU metrics (percentage)
            cpu_data = []
            base_cpu = np.random.uniform(10, 40)  # Base CPU usage (%)
            
            for t in time_points:
                # Simulate CPU usage with some randomness
                cpu_value = base_cpu + np.random.normal(0, 5)
                
                # Add some spikes randomly
                if np.random.random() < 0.05:  # 5% chance of a spike
                    cpu_value += np.random.uniform(20, 50)
                
                # Cap at 100%
                cpu_value = min(100, max(0, cpu_value))
                
                cpu_data.append({
                    'timestamp': t,
                    'value': cpu_value
                })
            
            metrics['cpu'][target['name']] = cpu_data
            
            # Memory metrics (MB)
            memory_data = []
            base_memory = np.random.uniform(100, 500)  # Base memory usage (MB)
            
            for t in time_points:
                # Simulate memory usage with some randomness and a slight upward trend
                time_factor = (t - start_time).total_seconds() / (end_time - start_time).total_seconds()
                memory_value = base_memory + (base_memory * 0.1 * time_factor) + np.random.normal(0, 20)
                
                # Add some spikes randomly
                if np.random.random() < 0.03:  # 3% chance of a spike
                    memory_value += np.random.uniform(50, 200)
                
                # Ensure positive value
                memory_value = max(0, memory_value)
                
                memory_data.append({
                    'timestamp': t,
                    'value': memory_value
                })
            
            metrics['memory'][target['name']] = memory_data
            
            # Network metrics (KB/s)
            network_data = []
            base_network = np.random.uniform(50, 200)  # Base network usage (KB/s)
            
            for t in time_points:
                # Simulate network usage with some randomness
                network_value = base_network + np.random.normal(0, 30)
                
                # Add some spikes randomly
                if np.random.random() < 0.08:  # 8% chance of a spike
                    network_value += np.random.uniform(100, 500)
                
                # Ensure positive value
                network_value = max(0, network_value)
                
                network_data.append({
                    'timestamp': t,
                    'value': network_value
                })
            
            metrics['network'][target['name']] = network_data
        
        return metrics
    
    def _analyze_resource_usage(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze resource usage from collected metrics.
        
        Args:
            metrics: Dictionary containing collected metrics
            
        Returns:
            Dict containing resource usage analysis
        """
        resource_usage = {}
        
        # Analyze CPU usage
        for pod_name, cpu_data in metrics['cpu'].items():
            if not cpu_data:
                continue
                
            cpu_values = [item['value'] for item in cpu_data]
            avg_cpu = np.mean(cpu_values)
            max_cpu = np.max(cpu_values)
            
            resource_usage[f"{pod_name}_cpu"] = {
                'resource': f"{pod_name} (CPU)",
                'average': round(avg_cpu, 2),
                'maximum': round(max_cpu, 2),
                'utilization': round(avg_cpu, 2),
                'status': 'critical' if max_cpu > 90 else ('warning' if max_cpu > 70 else 'normal')
            }
        
        # Analyze Memory usage
        for pod_name, memory_data in metrics['memory'].items():
            if not memory_data:
                continue
                
            memory_values = [item['value'] for item in memory_data]
            avg_memory = np.mean(memory_values)
            max_memory = np.max(memory_values)
            
            # Assume a pod with 2GB limit for the utilization calculation
            memory_limit = 2048  # MB
            utilization = (avg_memory / memory_limit) * 100
            
            resource_usage[f"{pod_name}_memory"] = {
                'resource': f"{pod_name} (Memory)",
                'average': round(avg_memory, 2),
                'maximum': round(max_memory, 2),
                'utilization': round(utilization, 2),
                'status': 'critical' if utilization > 90 else ('warning' if utilization > 70 else 'normal')
            }
        
        # Analyze Network usage
        for pod_name, network_data in metrics['network'].items():
            if not network_data:
                continue
                
            network_values = [item['value'] for item in network_data]
            avg_network = np.mean(network_values)
            max_network = np.max(network_values)
            
            resource_usage[f"{pod_name}_network"] = {
                'resource': f"{pod_name} (Network)",
                'average': round(avg_network, 2),
                'maximum': round(max_network, 2),
                'units': 'KB/s'
            }
        
        return resource_usage
    
    def _detect_anomalies(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in the metrics data.
        
        Args:
            metrics: Dictionary containing collected metrics
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Detect CPU anomalies
        for pod_name, cpu_data in metrics['cpu'].items():
            if not cpu_data:
                continue
                
            cpu_values = [item['value'] for item in cpu_data]
            cpu_times = [item['timestamp'] for item in cpu_data]
            
            # Calculate mean and standard deviation
            mean = np.mean(cpu_values)
            std = np.std(cpu_values)
            
            # Detect outliers (values beyond 3 standard deviations)
            threshold = mean + (3 * std)
            
            # Find outlier points
            outliers = [(cpu_times[i], val) for i, val in enumerate(cpu_values) if val > threshold and val > 70]
            
            if outliers:
                # Create chart data for visualization
                chart_data = []
                for i, val in enumerate(cpu_values):
                    chart_data.append({
                        'timestamp': cpu_times[i].strftime('%Y-%m-%d %H:%M:%S'),
                        'value': val,
                        'is_anomaly': val > threshold and val > 70
                    })
                
                anomalies.append({
                    'resource': f"{pod_name} (CPU)",
                    'description': f"CPU usage spikes detected ({len(outliers)} occurrences)",
                    'severity': 'High' if max(cpu_values) > 90 else 'Medium',
                    'deviation': f"{round((max(cpu_values) - mean) / mean * 100, 1)}% above average",
                    'chart_data': chart_data
                })
        
        # Detect Memory anomalies
        for pod_name, memory_data in metrics['memory'].items():
            if not memory_data:
                continue
                
            memory_values = [item['value'] for item in memory_data]
            memory_times = [item['timestamp'] for item in memory_data]
            
            # Calculate trend using linear regression
            x = np.arange(len(memory_values))
            slope, _ = np.polyfit(x, memory_values, 1)
            
            # Check for memory leaks (consistent upward trend)
            if slope > 2.0:  # Memory increases by more than 2MB per minute on average
                # Create chart data for visualization
                chart_data = []
                for i, val in enumerate(memory_values):
                    chart_data.append({
                        'timestamp': memory_times[i].strftime('%Y-%m-%d %H:%M:%S'),
                        'value': val
                    })
                
                anomalies.append({
                    'resource': f"{pod_name} (Memory)",
                    'description': f"Potential memory leak detected (trend: +{round(slope, 2)} MB/minute)",
                    'severity': 'High' if slope > 5.0 else 'Medium',
                    'growth_rate': f"{round(slope * 60, 2)} MB/hour",
                    'chart_data': chart_data
                })
        
        # Detect Network anomalies
        for pod_name, network_data in metrics['network'].items():
            if not network_data:
                continue
                
            network_values = [item['value'] for item in network_data]
            network_times = [item['timestamp'] for item in network_data]
            
            # Calculate mean and standard deviation
            mean = np.mean(network_values)
            std = np.std(network_values)
            
            # Detect outliers (values beyond 3 standard deviations)
            threshold = mean + (3 * std)
            
            # Find outlier points
            outliers = [(network_times[i], val) for i, val in enumerate(network_values) if val > threshold and val > 300]
            
            if outliers and len(outliers) > 2:  # Require at least 3 outliers to report
                # Create chart data for visualization
                chart_data = []
                for i, val in enumerate(network_values):
                    chart_data.append({
                        'timestamp': network_times[i].strftime('%Y-%m-%d %H:%M:%S'),
                        'value': val,
                        'is_anomaly': val > threshold and val > 300
                    })
                
                anomalies.append({
                    'resource': f"{pod_name} (Network)",
                    'description': f"Network usage spikes detected ({len(outliers)} occurrences)",
                    'severity': 'Medium',
                    'deviation': f"{round((max(network_values) - mean) / mean * 100, 1)}% above average",
                    'chart_data': chart_data
                })
        
        return anomalies
    
    def _format_raw_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format raw metrics for analysis results.
        
        Args:
            metrics: Dictionary containing collected metrics
            
        Returns:
            Dict containing formatted metrics
        """
        formatted_metrics = {}
        
        # Format CPU metrics
        cpu_data = []
        for pod_name, pod_metrics in metrics['cpu'].items():
            for metric in pod_metrics:
                cpu_data.append({
                    'pod': pod_name,
                    'timestamp': metric['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'value': metric['value'],
                    'unit': '%'
                })
        formatted_metrics['cpu'] = cpu_data
        
        # Format Memory metrics
        memory_data = []
        for pod_name, pod_metrics in metrics['memory'].items():
            for metric in pod_metrics:
                memory_data.append({
                    'pod': pod_name,
                    'timestamp': metric['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'value': metric['value'],
                    'unit': 'MB'
                })
        formatted_metrics['memory'] = memory_data
        
        # Format Network metrics
        network_data = []
        for pod_name, pod_metrics in metrics['network'].items():
            for metric in pod_metrics:
                network_data.append({
                    'pod': pod_name,
                    'timestamp': metric['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'value': metric['value'],
                    'unit': 'KB/s'
                })
        formatted_metrics['network'] = network_data
        
        return formatted_metrics
