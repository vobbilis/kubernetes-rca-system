from typing import Dict, List, Any, Optional
import json
import uuid
from utils.llm_client_improved import LLMClient

class MCPAgent:
    """
    Base class for all Model Context Protocol (MCP) agents
    that use LLMs for reasoning and analysis.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the MCP agent with a Kubernetes client and LLM provider.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        self.k8s_client = k8s_client
        self.llm_client = LLMClient(provider=provider)
        self.findings = []
        self.reasoning_steps = []
        self.agent_id = str(uuid.uuid4())
        self.agent_name = self.__class__.__name__
        
        # Initialize agent-specific tools
        self.tools = self._get_agent_tools()
        
        # Prepare system prompt for this specific agent
        self.system_prompt = self._get_system_prompt()
    
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform analysis using the MCP approach.
        
        Args:
            context: Dictionary containing context information for the analysis
            
        Returns:
            Dict containing analysis results
        """
        try:
            # Reset any previous state
            self.reset()
            
            # Run analysis with the LLM
            result = self.llm_client.analyze(
                context=context,
                tools=self.tools,
                system_prompt=self.system_prompt
            )
            
            # Process the results
            self._process_llm_results(result)
            
            # Return the findings and reasoning
            return self.get_results()
            
        except Exception as e:
            self.add_reasoning_step(
                observation=f"Error occurred during {self.agent_name} analysis: {str(e)}",
                conclusion="Unable to complete analysis due to an error"
            )
            return {
                'error': str(e),
                'findings': self.findings,
                'reasoning_steps': self.reasoning_steps
            }
    
    def _get_agent_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools available to this agent.
        Should be overridden by subclasses to provide agent-specific tools.
        
        Returns:
            List of tool definitions
        """
        # Base tools available to all agents
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_pod_list",
                    "description": "Get a list of pods in the specified namespace",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "description": "The Kubernetes namespace"
                            }
                        },
                        "required": ["namespace"]
                    }
                }
            }
        ]
    
    def _get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent.
        Should be overridden by subclasses to provide agent-specific instructions.
        
        Returns:
            String containing the system prompt
        """
        return f"""You are a Kubernetes {self.agent_name} expert agent. 
Your goal is to analyze Kubernetes resources and identify potential issues or root causes of problems.
Follow these steps in your analysis:

1. Carefully review the provided information
2. Use available tools to gather additional context as needed
3. Apply expert knowledge to identify patterns, anomalies, and potential issues
4. Explain your reasoning clearly, connecting observations to conclusions
5. Recommend specific actions to resolve any issues found

Think step-by-step and be thorough in your analysis.
"""
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool based on its name and arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            context: Additional context for the tool execution (optional)
            
        Returns:
            Result of the tool execution
        """
        # Set up the LLM client to use our tool execution method
        # We'll adapt to the new interface with the context parameter
        
        # Execute the tool
        result = self._execute_tool_internal(tool_name, arguments)
        
        # Format result as expected by the improved interface
        return {
            "result": result,
            "execution_status": "success",
            "tool_name": tool_name,
            "arguments": arguments
        }
    
    def _execute_tool_internal(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Internal method to execute tools based on their name.
        Dispatches to the appropriate implementation.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        # Common tools for all agents
        if tool_name == "get_pod_list":
            return self.k8s_client.get_pods(arguments["namespace"])
        
        # Dispatch to agent-specific tool implementations
        method_name = f"_tool_{tool_name}"
        if hasattr(self, method_name) and callable(getattr(self, method_name)):
            return getattr(self, method_name)(arguments)
        
        raise ValueError(f"Unknown tool: {tool_name}")
    
    def _process_llm_results(self, result: Dict[str, Any]) -> None:
        """
        Process the results from the LLM analysis to extract findings.
        
        Args:
            result: The result from the LLM analysis
        """
        # Record the reasoning steps from the LLM
        if "reasoning_steps" in result:
            for step in result["reasoning_steps"]:
                if step["type"] == "thinking":
                    self.add_reasoning_step(
                        observation=f"Analysis step {step['step']}",
                        conclusion=step["content"]
                    )
                elif step["type"] == "tool_call":
                    self.add_reasoning_step(
                        observation=f"Using tool: {step['tool']}",
                        conclusion=f"Arguments: {json.dumps(step['arguments'])}"
                    )
                elif step["type"] == "observation":
                    self.add_reasoning_step(
                        observation=f"Tool {step['tool']} result",
                        conclusion=f"Observed: {json.dumps(step['result'])}"
                    )
        
        # Add a final reasoning step with the LLM's final analysis
        if "final_analysis" in result:
            self.add_reasoning_step(
                observation="Final analysis by agent",
                conclusion=result["final_analysis"]
            )
        
        # Extract findings from the final analysis
        # This is a simple parsing approach - in practice, you might want to
        # use a more structured approach or have the LLM output in a specific format
        if "final_analysis" in result:
            # Use a simple heuristic to extract findings from the text
            # Looking for sections like "Issue:", "Problem:", "Finding:", etc.
            analysis = result["final_analysis"]
            lines = analysis.split('\n')
            
            current_finding = {}
            for line in lines:
                line = line.strip()
                
                # Look for section headers that might indicate findings
                if line.startswith("Issue:") or line.startswith("Finding:") or line.startswith("Problem:"):
                    # If we were already collecting a finding, save it
                    if current_finding and "issue" in current_finding:
                        self.add_finding(**current_finding)
                    
                    # Start a new finding
                    current_finding = {
                        "component": "Unknown",
                        "issue": line.split(":", 1)[1].strip() if ":" in line else line,
                        "severity": "medium",
                        "evidence": "",
                        "recommendation": ""
                    }
                
                elif line.startswith("Component:") or line.startswith("Service:") or line.startswith("Resource:"):
                    if current_finding:
                        current_finding["component"] = line.split(":", 1)[1].strip()
                
                elif line.startswith("Severity:"):
                    if current_finding:
                        severity = line.split(":", 1)[1].strip().lower()
                        if severity in ["critical", "high", "medium", "low", "info"]:
                            current_finding["severity"] = severity
                
                elif line.startswith("Evidence:") or line.startswith("Observation:"):
                    if current_finding:
                        current_finding["evidence"] = line.split(":", 1)[1].strip()
                
                elif line.startswith("Recommendation:") or line.startswith("Solution:") or line.startswith("Action:"):
                    if current_finding:
                        current_finding["recommendation"] = line.split(":", 1)[1].strip()
            
            # Add the last finding if any
            if current_finding and "issue" in current_finding:
                self.add_finding(**current_finding)
    
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
            'agent': self.agent_name,
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
            'agent': self.agent_name,
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
            'agent': self.agent_name,
            'findings': self.findings,
            'reasoning_steps': self.reasoning_steps
        }
    
    def reset(self):
        """Reset the agent's state for a new analysis."""
        self.findings = []
        self.reasoning_steps = []