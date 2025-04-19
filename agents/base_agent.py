class BaseAgent:
    """
    Base class for all specialized agents in the Kubernetes root cause analysis system.
    Provides common functionality and interface for all agents.
    """
    
    def __init__(self, k8s_client):
        """
        Initialize the base agent.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
        """
        self.k8s_client = k8s_client
        self.findings = []
        self.reasoning_steps = []
    
    def analyze(self, namespace, context=None, **kwargs):
        """
        Perform analysis based on the agent's specialty.
        This method should be overridden by child classes.
        
        Args:
            namespace: The Kubernetes namespace to analyze
            context: The Kubernetes context to use
            **kwargs: Additional parameters for the analysis
            
        Returns:
            dict: Results of the analysis
        """
        raise NotImplementedError("Each agent must implement its own analyze method")
    
    def add_finding(self, component, issue, severity, evidence, recommendation):
        """
        Add a finding to the agent's findings list.
        
        Args:
            component: The component where the issue was found
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
            'timestamp': self.k8s_client.get_current_time()
        }
        self.findings.append(finding)
    
    def add_reasoning_step(self, observation, conclusion):
        """
        Add a reasoning step to document the agent's analysis process.
        
        Args:
            observation: What the agent observed in the data
            conclusion: What the agent concluded from the observation
        """
        step = {
            'observation': observation,
            'conclusion': conclusion,
            'timestamp': self.k8s_client.get_current_time()
        }
        self.reasoning_steps.append(step)
    
    def get_results(self):
        """
        Get the complete results of the agent's analysis.
        
        Returns:
            dict: Results including findings and reasoning steps
        """
        return {
            'findings': self.findings,
            'reasoning_steps': self.reasoning_steps
        }
    
    def reset(self):
        """Reset the agent's state for a new analysis."""
        self.findings = []
        self.reasoning_steps = []
