from agents.metrics_agent import MetricsAgent
from agents.logs_agent import LogsAgent
from agents.traces_agent import TracesAgent
from agents.topology_agent import TopologyAgent
from agents.events_agent import EventsAgent

class Coordinator:
    """
    Coordinator agent that orchestrates the analysis flow between specialized agents.
    Responsible for delegating tasks, correlating findings, and producing a comprehensive analysis.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the coordinator agent with all specialized agents.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        self.k8s_client = k8s_client
        
        # Initialize specialized agents
        self.metrics_agent = MetricsAgent(k8s_client)
        self.logs_agent = LogsAgent(k8s_client)
        self.traces_agent = TracesAgent(k8s_client)
        self.topology_agent = TopologyAgent(k8s_client)
        self.events_agent = EventsAgent(k8s_client)
        
        # Map of analysis types to their corresponding agents
        self.agent_map = {
            'comprehensive': self._run_comprehensive_analysis,
            'metrics': self.metrics_agent.analyze,
            'logs': self.logs_agent.analyze,
            'traces': self.traces_agent.analyze,
            'topology': self.topology_agent.analyze,
            'events': self.events_agent.analyze
        }
    
    def run_analysis(self, analysis_type, namespace, context=None, **kwargs):
        """
        Run an analysis based on the specified type.
        
        Args:
            analysis_type: Type of analysis to run (comprehensive, metrics, logs, etc.)
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Analysis results from the relevant agent(s)
        """
        try:
            if analysis_type not in self.agent_map:
                return {'error': f"Unknown analysis type: {analysis_type}"}
            
            # Run the analysis using the appropriate agent/method
            results = self.agent_map[analysis_type](namespace=namespace, context=context, **kwargs)
            
            # Add metadata to the results
            results['metadata'] = {
                'analysis_type': analysis_type,
                'namespace': namespace,
                'context': context or self.k8s_client.get_current_context(),
                'timestamp': self.k8s_client.get_current_time()
            }
            
            return results
        
        except Exception as e:
            return {'error': str(e)}
    
    def _run_comprehensive_analysis(self, namespace, context=None, **kwargs):
        """
        Run a comprehensive analysis using all specialized agents.
        
        Args:
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Comprehensive analysis results from all agents
        """
        # Reset all agents
        self._reset_agents()
        
        # Run analysis with each specialized agent
        metrics_results = self.metrics_agent.analyze(namespace, context, **kwargs)
        logs_results = self.logs_agent.analyze(namespace, context, **kwargs)
        topology_results = self.topology_agent.analyze(namespace, context, **kwargs)
        events_results = self.events_agent.analyze(namespace, context, **kwargs)
        traces_results = self.traces_agent.analyze(namespace, context, **kwargs)
        
        # Correlate findings across agents
        correlated_findings = self._correlate_findings(
            metrics_results.get('findings', []),
            logs_results.get('findings', []),
            topology_results.get('findings', []),
            events_results.get('findings', []),
            traces_results.get('findings', [])
        )
        
        # Combine all results
        comprehensive_results = {
            'correlated_findings': correlated_findings,
            'agent_results': {
                'metrics': metrics_results,
                'logs': logs_results,
                'topology': topology_results,
                'events': events_results,
                'traces': traces_results
            },
            'root_causes': self._identify_root_causes(correlated_findings)
        }
        
        return comprehensive_results
    
    def _correlate_findings(self, *agent_findings_lists):
        """
        Correlate findings from different agents to identify related issues.
        
        Args:
            *agent_findings_lists: Lists of findings from each agent
            
        Returns:
            list: Correlated findings with relationships identified
        """
        # Flatten all findings into a single list
        all_findings = []
        for findings_list in agent_findings_lists:
            all_findings.extend(findings_list)
        
        # Group findings by component
        component_map = {}
        for finding in all_findings:
            component = finding['component']
            if component not in component_map:
                component_map[component] = []
            component_map[component].append(finding)
        
        # Create correlated findings
        correlated_findings = []
        for component, findings in component_map.items():
            if len(findings) > 1:
                # Multiple issues found for the same component
                correlated_findings.append({
                    'component': component,
                    'related_findings': findings,
                    'correlation_type': 'component',
                    'severity': max([f['severity'] for f in findings], key=lambda s: ['info', 'low', 'medium', 'high', 'critical'].index(s))
                })
        
        # TODO: Implement more sophisticated correlation logic based on timing, causality, etc.
        
        return correlated_findings
    
    def _identify_root_causes(self, correlated_findings):
        """
        Analyze correlated findings to identify potential root causes.
        
        Args:
            correlated_findings: List of correlated findings
            
        Returns:
            list: Identified root causes with explanations
        """
        root_causes = []
        
        # Simple algorithm: findings with highest severity that have related findings
        # are more likely to be root causes
        for finding in correlated_findings:
            if finding['severity'] in ['critical', 'high']:
                related_count = len(finding['related_findings'])
                if related_count > 1:
                    root_causes.append({
                        'component': finding['component'],
                        'related_findings_count': related_count,
                        'severity': finding['severity'],
                        'explanation': f"High severity issue with {related_count} related findings indicates a potential root cause."
                    })
        
        # TODO: Implement more sophisticated root cause analysis
        
        return root_causes
    
    def _reset_agents(self):
        """Reset all agents to prepare for a new analysis."""
        self.metrics_agent.reset()
        self.logs_agent.reset()
        self.traces_agent.reset()
        self.topology_agent.reset()
        self.events_agent.reset()
