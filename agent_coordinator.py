import uuid
import time
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

from agents.metrics_agent import MetricsAgent
from agents.logs_agent import LogsAgent
from agents.traces_agent import TracesAgent
from agents.topology_agent import TopologyAgent
from agents.events_agent import EventsAgent
from utils.kubernetes_client import KubernetesClient
from utils.data_processing import correlate_findings, merge_results

class AgentCoordinator:
    """
    Coordinates the activities of specialized agents for Kubernetes root cause analysis.
    Manages the workflow, distributes tasks, and correlates findings from different agents.
    """
    
    def __init__(self, k8s_client: KubernetesClient):
        """
        Initialize the coordinator with a Kubernetes client.
        
        Args:
            k8s_client: An initialized Kubernetes client for interacting with the cluster
        """
        self.k8s_client = k8s_client
        self.metrics_agent = MetricsAgent(k8s_client)
        self.logs_agent = LogsAgent(k8s_client)
        self.traces_agent = TracesAgent(k8s_client)
        self.topology_agent = TopologyAgent(k8s_client)
        self.events_agent = EventsAgent(k8s_client)
        
        # Store active analyses
        self.analyses = {}
        
    def init_analysis(self, config: Dict[str, Any]) -> str:
        """
        Initialize a new analysis with the given configuration.
        
        Args:
            config: Dictionary containing analysis configuration parameters
            
        Returns:
            analysis_id: Unique identifier for the analysis
        """
        analysis_id = str(uuid.uuid4())
        
        # Parse time range
        time_range_str = config.get('time_range', 'Last hour')
        end_time = datetime.now()
        
        if time_range_str == 'Last 15 minutes':
            start_time = end_time - timedelta(minutes=15)
        elif time_range_str == 'Last hour':
            start_time = end_time - timedelta(hours=1)
        elif time_range_str == 'Last 3 hours':
            start_time = end_time - timedelta(hours=3)
        elif time_range_str == 'Last 12 hours':
            start_time = end_time - timedelta(hours=12)
        elif time_range_str == 'Last 24 hours':
            start_time = end_time - timedelta(hours=24)
        else:
            start_time = end_time - timedelta(hours=1)  # Default to 1 hour
        
        # Store analysis configuration
        self.analyses[analysis_id] = {
            'config': config,
            'start_time': start_time,
            'end_time': end_time,
            'results': {},
            'status': 'initiated',
            'created_at': datetime.now()
        }
        
        return analysis_id
    
    def run_metrics_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run metrics analysis using the metrics agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing metrics analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        namespace = config['namespace']
        resource_type = config['resource_type']
        resource_name = config['resource_name']
        
        # Run metrics analysis
        metrics_results = self.metrics_agent.analyze(
            namespace=namespace,
            resource_type=resource_type.lower() if resource_type != 'All' else None,
            resource_name=resource_name if resource_name != 'All' else None,
            start_time=analysis['start_time'],
            end_time=analysis['end_time']
        )
        
        # Store results
        analysis['results']['metrics'] = metrics_results
        
        # Generate findings and conclusion
        findings = []
        
        if 'anomalies' in metrics_results and metrics_results['anomalies']:
            for anomaly in metrics_results['anomalies']:
                findings.append(f"Anomaly detected in {anomaly['resource']}: {anomaly['description']}")
        
        if 'resource_usage' in metrics_results:
            for resource, usage in metrics_results['resource_usage'].items():
                if usage.get('utilization', 0) > 80:
                    findings.append(f"High utilization ({usage['utilization']}%) detected for {resource}")
        
        # Generate conclusion
        if findings:
            conclusion = "Metrics analysis indicates performance issues related to resource utilization or spikes."
        else:
            conclusion = "No significant metric anomalies detected. Resource utilization is within normal ranges."
        
        return {
            "findings": findings,
            "conclusion": conclusion,
            "results": metrics_results
        }
    
    def run_logs_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run logs analysis using the logs agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing logs analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        namespace = config['namespace']
        resource_type = config['resource_type']
        resource_name = config['resource_name']
        
        # Run logs analysis
        logs_results = self.logs_agent.analyze(
            namespace=namespace,
            resource_type=resource_type.lower() if resource_type != 'All' else None,
            resource_name=resource_name if resource_name != 'All' else None,
            start_time=analysis['start_time'],
            end_time=analysis['end_time']
        )
        
        # Store results
        analysis['results']['logs'] = logs_results
        
        # Generate findings and conclusion
        findings = []
        
        if 'error_patterns' in logs_results and logs_results['error_patterns']:
            for pattern in logs_results['error_patterns']:
                findings.append(f"Error pattern detected: '{pattern['pattern']}' ({pattern['count']} occurrences)")
        
        # Generate conclusion
        if findings:
            conclusion = "Log analysis revealed error patterns that may indicate application issues."
        else:
            conclusion = "No significant error patterns detected in application logs."
        
        return {
            "findings": findings,
            "conclusion": conclusion,
            "results": logs_results
        }
    
    def run_topology_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run topology analysis using the topology agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing topology analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        namespace = config['namespace']
        
        # Run topology analysis
        topology_results = self.topology_agent.analyze(
            namespace=namespace,
            start_time=analysis['start_time'],
            end_time=analysis['end_time']
        )
        
        # Store results
        analysis['results']['topology'] = topology_results
        
        # Generate findings and conclusion
        findings = []
        
        if 'issues' in topology_results and topology_results['issues']:
            for issue in topology_results['issues']:
                findings.append(f"Topology issue: {issue['title']} affecting {', '.join(issue.get('affected_services', []))}")
        
        # Generate conclusion
        if findings:
            conclusion = "Topology analysis identified service connection issues that may impact application functionality."
        else:
            conclusion = "Service topology appears healthy with no detected connectivity issues."
        
        return {
            "findings": findings,
            "conclusion": conclusion,
            "results": topology_results
        }
    
    def run_events_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run events analysis using the events agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing events analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        namespace = config['namespace']
        
        # Run events analysis
        events_results = self.events_agent.analyze(
            namespace=namespace,
            start_time=analysis['start_time'],
            end_time=analysis['end_time']
        )
        
        # Store results
        analysis['results']['events'] = events_results
        
        # Generate findings and conclusion
        findings = []
        
        if 'critical_events' in events_results and events_results['critical_events']:
            for event in events_results['critical_events']:
                findings.append(f"Critical event: {event['reason']} on {event['involved_object']} - {event['message']}")
        
        # Generate conclusion
        if findings:
            conclusion = "Cluster events indicate operational issues that may affect application availability."
        else:
            conclusion = "No critical cluster events detected during the analysis period."
        
        return {
            "findings": findings,
            "conclusion": conclusion,
            "results": events_results
        }
    
    def run_traces_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run traces analysis using the traces agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing traces analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        namespace = config['namespace']
        
        # Run traces analysis
        traces_results = self.traces_agent.analyze(
            namespace=namespace,
            start_time=analysis['start_time'],
            end_time=analysis['end_time']
        )
        
        # Store results
        analysis['results']['traces'] = traces_results
        
        # Generate findings and conclusion
        findings = []
        
        if 'latency_issues' in traces_results and traces_results['latency_issues']:
            for issue in traces_results['latency_issues']:
                findings.append(f"Latency issue in {issue['service']}: {issue['description']}")
        
        # Generate conclusion
        if findings:
            conclusion = "Trace analysis identified request flow bottlenecks that impact application performance."
        else:
            conclusion = "Request flows appear normal with no significant latency issues detected."
        
        return {
            "findings": findings,
            "conclusion": conclusion,
            "results": traces_results
        }
    
    def correlate_findings(self, analysis_id: str) -> Dict[str, Any]:
        """
        Correlate findings from different agents to generate a comprehensive analysis.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing correlated findings and overall analysis results
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        results = analysis['results']
        
        # Correlate findings from different agents
        correlated_results = correlate_findings(results)
        
        # Update analysis status
        analysis['status'] = 'completed'
        analysis['completed_at'] = datetime.now()
        
        return correlated_results
    
    def generate_summary(self, analysis_id: str) -> Dict[str, Any]:
        """
        Generate a summary of the analysis results and identified root causes.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing a summary of the analysis
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        config = analysis['config']
        results = analysis['results']
        
        # Extract issue description
        issue_description = config.get('issue_description', 'Unspecified issue')
        
        # Initialize root causes and recommendations lists
        root_causes = []
        recommendations = []
        
        # Check metrics results
        if 'metrics' in results:
            metrics_results = results['metrics']
            
            if 'anomalies' in metrics_results and metrics_results['anomalies']:
                for anomaly in metrics_results['anomalies']:
                    root_causes.append({
                        'title': f"Resource Utilization Issue: {anomaly['resource']}",
                        'severity': 'High' if anomaly.get('severity', 'Medium') == 'High' else 'Medium',
                        'description': anomaly['description'],
                        'evidence': f"Metrics show {anomaly.get('deviation', 'abnormal')} values during the analysis period"
                    })
                    
                    recommendations.append({
                        'title': f"Optimize {anomaly['resource']} usage",
                        'description': f"Investigate and optimize resource usage for {anomaly['resource']}. Consider scaling the resource if necessary."
                    })
        
        # Check logs results
        if 'logs' in results:
            logs_results = results['logs']
            
            if 'error_patterns' in logs_results and logs_results['error_patterns']:
                for pattern in logs_results['error_patterns'][:2]:  # Limit to top 2 patterns
                    root_causes.append({
                        'title': f"Application Error: {pattern['pattern'][:50]}{'...' if len(pattern['pattern']) > 50 else ''}",
                        'severity': 'High' if pattern['count'] > 10 else 'Medium',
                        'description': f"Recurring error pattern detected in application logs",
                        'evidence': f"Error occurred {pattern['count']} times during the analysis period"
                    })
                    
                    recommendations.append({
                        'title': "Fix application errors",
                        'description': f"Investigate and fix the recurring error pattern in your application: '{pattern['pattern'][:100]}{'...' if len(pattern['pattern']) > 100 else ''}'."
                    })
        
        # Check topology results
        if 'topology' in results:
            topology_results = results['topology']
            
            if 'issues' in topology_results and topology_results['issues']:
                for issue in topology_results['issues']:
                    root_causes.append({
                        'title': f"Service Connectivity Issue: {issue['title']}",
                        'severity': issue.get('severity', 'Medium'),
                        'description': issue['description'],
                        'evidence': f"Topology analysis identified connectivity issues between services"
                    })
                    
                    recommendations.append({
                        'title': "Resolve service connectivity issues",
                        'description': f"Ensure proper network policies and service configurations for {', '.join(issue.get('affected_services', ['affected services']))}"
                    })
        
        # Check events results
        if 'events' in results:
            events_results = results['events']
            
            if 'critical_events' in events_results and events_results['critical_events']:
                for event in events_results['critical_events'][:2]:  # Limit to top 2 events
                    root_causes.append({
                        'title': f"Cluster Event: {event['reason']}",
                        'severity': 'High',
                        'description': event['message'],
                        'evidence': f"Cluster event recorded at {event['last_timestamp']}"
                    })
                    
                    recommendations.append({
                        'title': f"Address {event['reason']} events",
                        'description': f"Investigate and resolve the {event['reason']} events affecting {event['involved_object']}"
                    })
        
        # Check traces results
        if 'traces' in results:
            traces_results = results['traces']
            
            if 'latency_issues' in traces_results and traces_results['latency_issues']:
                for issue in traces_results['latency_issues']:
                    root_causes.append({
                        'title': f"Request Latency Issue: {issue['service']}",
                        'severity': issue.get('severity', 'Medium'),
                        'description': issue['description'],
                        'evidence': f"Trace analysis shows high latency in {issue['service']}"
                    })
                    
                    recommendations.append({
                        'title': f"Optimize {issue['service']} performance",
                        'description': f"Investigate performance bottlenecks in {issue['service']} and optimize request handling"
                    })
        
        # If no root causes were identified, add a default entry
        if not root_causes:
            root_causes.append({
                'title': "No significant issues detected",
                'severity': 'Low',
                'description': "The analysis did not identify any significant issues in the analyzed components",
                'evidence': "All analyzed metrics, logs, events, and traces are within normal parameters"
            })
            
            recommendations.append({
                'title': "Continue monitoring",
                'description': "Continue monitoring your application and consider expanding the analysis scope if issues persist"
            })
        
        # Return the summary
        return {
            'issue_description': issue_description,
            'analysis_period': {
                'start': analysis['start_time'].isoformat(),
                'end': analysis['end_time'].isoformat()
            },
            'scope': {
                'namespace': config['namespace'],
                'resource_type': config['resource_type'],
                'resource_name': config['resource_name']
            },
            'root_causes': root_causes,
            'recommendations': recommendations
        }
    
    def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dict containing the analysis status and metadata
        """
        if analysis_id not in self.analyses:
            raise ValueError(f"Analysis with ID {analysis_id} not found")
        
        analysis = self.analyses[analysis_id]
        
        return {
            'status': analysis['status'],
            'created_at': analysis['created_at'].isoformat(),
            'completed_at': analysis.get('completed_at', '').isoformat() if analysis.get('completed_at') else None,
            'config': analysis['config']
        }
    
    def list_analyses(self) -> List[Dict[str, Any]]:
        """
        List all analyses.
        
        Returns:
            List of dictionaries containing analysis metadata
        """
        return [
            {
                'id': analysis_id,
                'status': analysis['status'],
                'created_at': analysis['created_at'].isoformat(),
                'completed_at': analysis.get('completed_at', '').isoformat() if analysis.get('completed_at') else None,
                'namespace': analysis['config']['namespace'],
                'resource_type': analysis['config']['resource_type'],
                'resource_name': analysis['config']['resource_name']
            }
            for analysis_id, analysis in self.analyses.items()
        ]
