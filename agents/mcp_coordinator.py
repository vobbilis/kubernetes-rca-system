from typing import Dict, List, Any, Optional
import uuid
import time
import json
import networkx as nx

from agents.mcp_metrics_agent import MCPMetricsAgent
from agents.mcp_logs_agent import MCPLogsAgent
from agents.mcp_events_agent import MCPEventsAgent
from agents.mcp_topology_agent import MCPTopologyAgent
from agents.mcp_traces_agent import MCPTracesAgent
from agents.resource_analyzer import ResourceAnalyzer
from utils.llm_client import LLMClient

class MCPCoordinator:
    """
    Coordinator for Model Context Protocol agents.
    Manages the orchestration of different specialized agents and the correlation
    of their findings to perform root cause analysis.
    """
    
    def __init__(self, k8s_client, provider="openai"):
        """
        Initialize the MCP coordinator with a Kubernetes client.
        
        Args:
            k8s_client: An instance of the Kubernetes client for API interactions
            provider: LLM provider to use ("openai" or "anthropic")
        """
        self.k8s_client = k8s_client
        self.provider = provider
        self.llm_client = LLMClient(provider=provider)
        
        # Initialize agents
        self.metrics_agent = MCPMetricsAgent(k8s_client, provider)
        self.logs_agent = MCPLogsAgent(k8s_client, provider)
        self.events_agent = MCPEventsAgent(k8s_client, provider)
        self.topology_agent = MCPTopologyAgent(k8s_client, provider)
        self.traces_agent = MCPTracesAgent(k8s_client, provider)
        
        # Initialize the resource analyzer
        self.resource_analyzer = ResourceAnalyzer(k8s_client)
        
        # Store analysis sessions
        self.analyses = {}
    
    def init_analysis(self, config: Dict[str, Any]) -> str:
        """
        Initialize a new analysis session.
        
        Args:
            config: Dictionary with analysis configuration
            
        Returns:
            String with the analysis ID
        """
        analysis_id = str(uuid.uuid4())
        
        self.analyses[analysis_id] = {
            "id": analysis_id,
            "config": config,
            "status": "initialized",
            "started_at": time.time(),
            "completed_at": None,
            "results": {},
            "summary": None
        }
        
        return analysis_id
    
    def run_analysis(self, analysis_type: str, namespace: str, context: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Run an analysis based on the specified type.
        
        Args:
            analysis_type: Type of analysis to run ("comprehensive", "metrics", "logs", etc.)
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context to use (optional)
            **kwargs: Additional parameters for the analysis
            
        Returns:
            Dictionary with analysis results
        """
        # Create a new analysis session
        config = {
            "type": analysis_type,
            "namespace": namespace,
            "context": context,
            "parameters": kwargs
        }
        
        analysis_id = self.init_analysis(config)
        
        try:
            # Run the appropriate analysis
            if analysis_type == "comprehensive":
                result = self._run_comprehensive_analysis(analysis_id, namespace, context, **kwargs)
            elif analysis_type == "metrics":
                result = self.run_metrics_analysis(analysis_id)
            elif analysis_type == "logs":
                result = self.run_logs_analysis(analysis_id)
            elif analysis_type == "events":
                result = self.run_events_analysis(analysis_id)
            elif analysis_type == "topology":
                result = self.run_topology_analysis(analysis_id)
            elif analysis_type == "traces":
                result = self.run_traces_analysis(analysis_id)
            elif analysis_type == "resources":
                result = self.run_resource_analysis(analysis_id)
            else:
                return {"error": f"Unknown analysis type: {analysis_type}"}
            
            # Update analysis status
            self.analyses[analysis_id]["status"] = "completed"
            self.analyses[analysis_id]["completed_at"] = time.time()
            
            return result
            
        except Exception as e:
            # Update analysis status on error
            self.analyses[analysis_id]["status"] = "failed"
            self.analyses[analysis_id]["error"] = str(e)
            
            return {"error": str(e)}
    
    def run_metrics_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run metrics analysis using the metrics agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with metrics analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        context = analysis["config"].get("context")
        
        # Update analysis status
        analysis["status"] = "running_metrics"
        
        # Prepare context for the metrics agent
        agent_context = {
            "namespace": namespace,
            "context": context,
            "problem_description": analysis["config"]["parameters"].get("problem_description", "Perform a comprehensive metrics analysis of the cluster and workloads")
        }
        
        # Get metrics data
        try:
            agent_context["metrics"] = {
                "pods": self.k8s_client.get_pod_metrics(namespace) or {},
                "nodes": self.k8s_client.get_node_metrics() or {}
            }
        except Exception as e:
            agent_context["metrics_error"] = str(e)
        
        # Run the metrics agent
        metrics_results = self.metrics_agent.analyze(agent_context)
        
        # Store results
        analysis["results"]["metrics"] = metrics_results
        
        return metrics_results
    
    def run_logs_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run logs analysis using the logs agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with logs analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        context = analysis["config"].get("context")
        
        # Update analysis status
        analysis["status"] = "running_logs"
        
        # Prepare context for the logs agent
        agent_context = {
            "namespace": namespace,
            "context": context,
            "problem_description": analysis["config"]["parameters"].get("problem_description", "Perform a comprehensive logs analysis of the pods and containers")
        }
        
        # Get pod list
        pods = self.k8s_client.get_pods(namespace) or []
        
        # Get sample logs for key pods (limit to avoid context bloat)
        sample_logs = {}
        for pod in pods[:5]:  # Limit to first 5 pods for initial context
            pod_name = pod["metadata"]["name"]
            try:
                sample_logs[pod_name] = self.k8s_client.get_pod_logs(
                    namespace=namespace,
                    pod_name=pod_name,
                    tail_lines=50
                )
            except Exception as e:
                sample_logs[pod_name] = f"Error retrieving logs: {str(e)}"
        
        agent_context["logs"] = sample_logs
        agent_context["pods"] = pods
        
        # Run the logs agent
        logs_results = self.logs_agent.analyze(agent_context)
        
        # Store results
        analysis["results"]["logs"] = logs_results
        
        return logs_results
    
    def run_events_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run events analysis using the events agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with events analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        context = analysis["config"].get("context")
        
        # Update analysis status
        analysis["status"] = "running_events"
        
        # Prepare context for the events agent
        agent_context = {
            "namespace": namespace,
            "context": context,
            "problem_description": analysis["config"]["parameters"].get("problem_description", "Analyze Kubernetes events to identify control plane and operational issues")
        }
        
        # Get events
        try:
            agent_context["events"] = self.k8s_client.get_events(namespace=namespace) or []
        except Exception as e:
            agent_context["events_error"] = str(e)
        
        # Run the events agent
        events_results = self.events_agent.analyze(agent_context)
        
        # Store results
        analysis["results"]["events"] = events_results
        
        return events_results
    
    def run_topology_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run topology analysis using the topology agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with topology analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        context = analysis["config"].get("context")
        
        # Update analysis status
        analysis["status"] = "running_topology"
        
        # Prepare context for the topology agent
        agent_context = {
            "namespace": namespace,
            "context": context,
            "problem_description": analysis["config"]["parameters"].get("problem_description", "Analyze the service topology and connections between components")
        }
        
        # Get topology data
        try:
            pods = self.k8s_client.get_pods(namespace) or []
            services = self.k8s_client.get_services(namespace) or []
            deployments = self.k8s_client.get_deployments(namespace) or []
            
            agent_context["topology"] = {
                "pods": pods,
                "services": services,
                "deployments": deployments
            }
        except Exception as e:
            agent_context["topology_error"] = str(e)
        
        # Run the topology agent
        topology_results = self.topology_agent.analyze(agent_context)
        
        # Store results
        analysis["results"]["topology"] = topology_results
        
        return topology_results
    
    def run_traces_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run traces analysis using the traces agent.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with traces analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        context = analysis["config"].get("context")
        
        # Update analysis status
        analysis["status"] = "running_traces"
        
        # Prepare context for the traces agent
        agent_context = {
            "namespace": namespace,
            "context": context,
            "problem_description": analysis["config"]["parameters"].get("problem_description", "Analyze distributed traces to identify performance and communication issues")
        }
        
        # Typically trace information would be retrieved from a tracing backend
        # For initial context, we can provide minimal information
        agent_context["traces"] = {
            "available": self.k8s_client.are_traces_available(),
            "sample_traces": []
        }
        
        # Run the traces agent
        traces_results = self.traces_agent.analyze(agent_context)
        
        # Store results
        analysis["results"]["traces"] = traces_results
        
        return traces_results
        
    def run_resource_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """
        Run resource analysis using the resource analyzer.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with resource analysis results
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        namespace = analysis["config"]["namespace"]
        
        # Update analysis status
        analysis["status"] = "running_resource_analysis"
        
        # Run the resource analyzer
        try:
            resource_analysis = self.resource_analyzer.analyze_namespace_resources(namespace)
            
            # Reset findings and reasoning steps to ensure we get fresh results
            self.resource_analyzer.findings = []
            self.resource_analyzer.reasoning_steps = []
            
            # Store results
            analysis["results"]["resources"] = resource_analysis
            
            return resource_analysis
        except Exception as e:
            error_result = {
                "error": f"Resource analysis failed: {str(e)}",
                "findings": [],
                "reasoning_steps": [{
                    "observation": "Error during resource analysis",
                    "conclusion": str(e)
                }]
            }
            analysis["results"]["resources"] = error_result
            return error_result
    
    def _run_comprehensive_analysis(self, analysis_id: str, namespace: str, context: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """
        Run a comprehensive analysis using all agents.
        
        Args:
            analysis_id: Unique identifier for the analysis
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context to use (optional)
            **kwargs: Additional parameters for the analysis
            
        Returns:
            Dictionary with comprehensive analysis results
        """
        # First run the resource analysis as our starting point
        self.run_resource_analysis(analysis_id)
        
        # Then run each other individual analysis
        self.run_metrics_analysis(analysis_id)
        self.run_logs_analysis(analysis_id)
        self.run_events_analysis(analysis_id)
        self.run_topology_analysis(analysis_id)
        self.run_traces_analysis(analysis_id)
        
        # Correlate findings
        correlated_findings = self.correlate_findings(analysis_id)
        
        # Generate summary
        summary = self.generate_summary(analysis_id)
        
        # Return comprehensive results
        analysis = self.analyses[analysis_id]
        return {
            "resources": analysis["results"].get("resources", {}),
            "metrics": analysis["results"].get("metrics", {}),
            "logs": analysis["results"].get("logs", {}),
            "events": analysis["results"].get("events", {}),
            "topology": analysis["results"].get("topology", {}),
            "traces": analysis["results"].get("traces", {}),
            "correlated_findings": correlated_findings,
            "summary": summary
        }
    
    def correlate_findings(self, analysis_id: str) -> Dict[str, Any]:
        """
        Correlate findings from different agents to identify related issues.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with correlated findings
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        
        # Collect all findings from the individual analyses
        all_findings = []
        
        for analysis_type, results in analysis["results"].items():
            if "findings" in results:
                for finding in results["findings"]:
                    finding["source"] = analysis_type
                    all_findings.append(finding)
        
        # If no findings, return empty result
        if not all_findings:
            return {
                "correlated_groups": [],
                "root_causes": []
            }
        
        # Use the LLM to correlate the findings
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to correlate findings from different specialized agents to identify related issues
and determine the most likely root causes. Think carefully about how different symptoms and
issues might be connected to the same underlying problems.

When correlating findings:
1. Group related findings that are likely symptoms of the same underlying issue
2. Identify causal relationships between different findings
3. Determine the most likely root causes that explain the observed symptoms
4. Rank the root causes by likelihood and impact

Provide a clear explanation of your reasoning and the evidence supporting each potential root cause.
"""
        
        prompt = f"""## Kubernetes Analysis Findings

Below are findings from different specialized analysis agents examining a Kubernetes cluster.
Please correlate these findings to identify related issues and determine the most likely root causes.

### Findings
```json
{json.dumps(all_findings, indent=2)}
```

Please group related findings, identify causal relationships, and determine the most likely root causes.
Format your response as follows:

1. First, list groups of related findings with IDs for each group
2. Then, for each group, identify the most likely root cause(s) with an explanation
3. Finally, provide a ranked list of root causes with supporting evidence
"""
        
        # Create a context for the coordinator LLM
        try:
            # Get correlation analysis from LLM
            correlation_result = self.llm_client.analyze(
                context={"problem_description": prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Store the correlation in the analysis
            analysis["correlated_findings"] = {
                "raw_findings": all_findings,
                "correlation_analysis": correlation_result.get("final_analysis", "")
            }
            
            # Parse the correlation analysis to extract structured data
            # In a real implementation, we might use a more structured approach
            # or have the LLM output in a specific format
            
            # For now, return the raw analysis
            return {
                "findings_count": len(all_findings),
                "correlation_analysis": correlation_result.get("final_analysis", ""),
                "reasoning_steps": correlation_result.get("reasoning_steps", [])
            }
            
        except Exception as e:
            return {
                "error": f"Error correlating findings: {str(e)}",
                "raw_findings": all_findings
            }
    
    def generate_summary(self, analysis_id: str) -> Dict[str, Any]:
        """
        Generate a summary of the analysis results.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with analysis summary
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        
        # Use the LLM to generate a summary
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to generate a clear, concise summary of the analysis results that highlights
the most important findings, the identified root causes, and recommended actions.

The summary should be structured as follows:
1. Overview: Brief description of the analyzed system and the issues found
2. Key Findings: The most significant issues identified across all analysis types
3. Root Causes: The underlying problems that are causing the observed issues
4. Recommendations: Clear, actionable steps to resolve the issues
5. Next Steps: Suggested further investigations if needed
"""
        
        # Create a condensed version of the results for the prompt
        results_summary = {}
        
        for analysis_type, results in analysis["results"].items():
            if "findings" in results:
                results_summary[analysis_type] = {
                    "findings": results["findings"],
                    "findings_count": len(results["findings"])
                }
        
        # Add correlated findings if available
        if "correlated_findings" in analysis:
            results_summary["correlation"] = analysis["correlated_findings"]
        
        prompt = f"""## Kubernetes Analysis Results Summary

Please generate a comprehensive summary of the analysis results for a Kubernetes cluster.

### Analysis Configuration
- Namespace: {analysis["config"]["namespace"]}
- Analysis Type: {analysis["config"]["type"]}

### Results Overview
```json
{json.dumps(results_summary, indent=2)}
```

Please provide a clear, concise summary that highlights the most important findings,
identified root causes, and recommended actions to resolve the issues.
"""
        
        try:
            # Get summary from LLM
            summary_result = self.llm_client.analyze(
                context={"problem_description": prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Store the summary in the analysis
            summary = summary_result.get("final_analysis", "")
            analysis["summary"] = summary
            
            return {
                "summary": summary,
                "reasoning_steps": summary_result.get("reasoning_steps", [])
            }
            
        except Exception as e:
            return {
                "error": f"Error generating summary: {str(e)}"
            }
    
    def get_analysis_status(self, analysis_id: str) -> Dict[str, Any]:
        """
        Get the status of an analysis.
        
        Args:
            analysis_id: Unique identifier for the analysis
            
        Returns:
            Dictionary with analysis status
        """
        if analysis_id not in self.analyses:
            return {"error": "Invalid analysis ID"}
        
        analysis = self.analyses[analysis_id]
        
        return {
            "id": analysis["id"],
            "status": analysis["status"],
            "config": analysis["config"],
            "started_at": analysis["started_at"],
            "completed_at": analysis["completed_at"],
            "duration": (analysis["completed_at"] or time.time()) - analysis["started_at"],
            "result_types": list(analysis["results"].keys()) if "results" in analysis else [],
            "has_summary": "summary" in analysis and analysis["summary"] is not None
        }
    
    def list_analyses(self) -> List[Dict[str, Any]]:
        """
        List all analyses.
        
        Returns:
            List of dictionaries with analysis metadata
        """
        return [
            {
                "id": analysis_id,
                "status": analysis["status"],
                "namespace": analysis["config"]["namespace"],
                "type": analysis["config"]["type"],
                "started_at": analysis["started_at"],
                "completed_at": analysis["completed_at"]
            }
            for analysis_id, analysis in self.analyses.items()
        ]
        
    def generate_hypotheses(self, component: str, finding: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate potential root cause hypotheses for a specific component and finding.
        
        Args:
            component: Component identifier (e.g., "Pod/nginx")
            finding: Finding data for the component
            
        Returns:
            List of hypothesis objects
        """
        # Create a prompt for the LLM to generate hypotheses
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to generate potential root cause hypotheses for a specific Kubernetes component issue.
For each hypothesis:
1. Provide a clear description of the potential root cause
2. Assign a confidence score (0.0-1.0) based on how likely this hypothesis is given the evidence
3. Suggest investigation steps to confirm or rule out this hypothesis
4. List any related components that might be affected

Think broadly about different categories of potential causes:
- Application issues (code bugs, misconfigurations)
- Resource constraints (CPU, memory, disk)
- Networking issues (connectivity, DNS, service discovery)
- Configuration issues (environment variables, secrets, ConfigMaps)
- Infrastructure issues (node problems, scheduling)
- Security issues (permissions, RBAC, PSPs)

Return a JSON array of hypothesis objects with the following structure:
[
  {
    "description": "Clear description of the potential root cause",
    "confidence": 0.8, // Value between 0.0 and 1.0
    "investigation_steps": ["Step 1 to investigate", "Step 2 to investigate"],
    "related_components": ["Component1", "Component2"]
  }
]
"""
        
        # Construct the user prompt with the component and finding details
        component_type = component.split('/')[0] if '/' in component else 'Resource'
        component_name = component.split('/')[1] if '/' in component else component
        
        issue = finding.get('issue', 'Unknown issue')
        severity = finding.get('severity', 'medium')
        evidence = finding.get('evidence', 'No additional evidence')
        
        user_prompt = f"""## Kubernetes Issue Details

**Component Type:** {component_type}
**Component Name:** {component_name}
**Issue:** {issue}
**Severity:** {severity}
**Evidence:** {evidence}

Based on this information, generate 3-5 potential root cause hypotheses that might explain the observed issue.
For each hypothesis, provide a confidence score, investigation steps, and related components.

Output your response as a JSON array of hypothesis objects."""

        try:
            # Get hypotheses from LLM
            result = self.llm_client.analyze(
                context={"problem_description": user_prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Parse the hypotheses from the result
            hypotheses = result.get("hypotheses", [])
            
            # If no hypotheses were found in the expected field, try to find a JSON array in the final analysis
            if not hypotheses and "final_analysis" in result:
                try:
                    # Try to extract JSON from the text
                    analysis_text = result["final_analysis"]
                    json_start = analysis_text.find("[")
                    json_end = analysis_text.rfind("]") + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = analysis_text[json_start:json_end]
                        hypotheses = json.loads(json_str)
                except Exception as e:
                    print(f"Error extracting hypotheses from final analysis: {e}")
            
            # If still no hypotheses, create a default one
            if not hypotheses:
                hypotheses = [
                    {
                        "description": f"Unknown issue with {component}",
                        "confidence": 0.5,
                        "investigation_steps": [
                            f"Check logs for {component}",
                            f"Verify configuration of {component}",
                            f"Check related resources and dependencies"
                        ],
                        "related_components": []
                    }
                ]
            
            return hypotheses
            
        except Exception as e:
            print(f"Error generating hypotheses: {e}")
            # Return a default hypothesis on error
            return [
                {
                    "description": f"Error occurred while analyzing {component}: {str(e)}",
                    "confidence": 0.3,
                    "investigation_steps": [
                        "Check system connectivity",
                        "Verify LLM API access",
                        "Try again with more specific information"
                    ],
                    "related_components": []
                }
            ]
    
    def get_investigation_plan(self, component: str, finding: Dict[str, Any], hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate an investigation plan for a specific hypothesis.
        
        Args:
            component: Component identifier (e.g., "Pod/nginx")
            finding: Finding data for the component
            hypothesis: Hypothesis to investigate
            
        Returns:
            Investigation plan object
        """
        # Create a prompt for the LLM to generate an investigation plan
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to create a detailed investigation plan to confirm or rule out a specific hypothesis
about a Kubernetes component issue.

Include the following in your investigation plan:
1. A list of specific steps to gather more information, in order of priority
2. For each step, include the specific commands or techniques to use
3. Expected results if the hypothesis is correct
4. Alternative explanations to consider
5. Next steps based on different possible outcomes

Think about how to efficiently validate or invalidate the hypothesis. Consider:
- Log analysis techniques
- Specific kubectl commands to run
- Configuration checks
- Dependency verification
- Resource utilization analysis
- Network connectivity tests

Return a structured investigation plan in JSON format.
"""
        
        # Construct the user prompt with the component, finding, and hypothesis details
        component_type = component.split('/')[0] if '/' in component else 'Resource'
        component_name = component.split('/')[1] if '/' in component else component
        
        issue = finding.get('issue', 'Unknown issue')
        evidence = finding.get('evidence', 'No additional evidence')
        hypothesis_desc = hypothesis.get('description', 'Unknown hypothesis')
        
        user_prompt = f"""## Investigation Context

**Component:** {component_type}/{component_name}
**Issue:** {issue}
**Evidence:** {evidence}
**Hypothesis:** {hypothesis_desc}

Create a detailed investigation plan to confirm or rule out this hypothesis.
Include specific steps, commands, expected results, and next steps based on outcomes.

Output your response as a JSON object with the following structure:
{{
  "steps": [
    {{
      "description": "Check pod logs",
      "commands": ["kubectl logs pod-name -n namespace"],
      "expected_if_true": "What we would see if the hypothesis is correct",
      "expected_if_false": "What we would see if the hypothesis is incorrect"
    }}
  ],
  "evidence_needed": ["List of evidence types needed to confirm/reject"],
  "conclusion_criteria": "Criteria to reach a conclusion",
  "next_steps": [
    {{
      "description": "What to do next based on findings",
      "type": "command/analysis/correlation"
    }}
  ]
}}"""

        try:
            # Get investigation plan from LLM
            result = self.llm_client.analyze(
                context={"problem_description": user_prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Parse the investigation plan from the result
            plan = result.get("investigation_plan", {})
            
            # If no plan was found in the expected field, try to find a JSON object in the final analysis
            if not plan and "final_analysis" in result:
                try:
                    # Try to extract JSON from the text
                    analysis_text = result["final_analysis"]
                    json_start = analysis_text.find("{")
                    json_end = analysis_text.rfind("}") + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = analysis_text[json_start:json_end]
                        plan = json.loads(json_str)
                except Exception as e:
                    print(f"Error extracting investigation plan from final analysis: {e}")
            
            # If still no plan, create a default one
            if not plan:
                plan = {
                    "steps": [
                        {
                            "description": f"Check logs for {component}",
                            "commands": [f"kubectl logs {component.split('/')[1]} -n default"],
                            "expected_if_true": "Error messages related to the hypothesis",
                            "expected_if_false": "No relevant error messages"
                        },
                        {
                            "description": f"Examine resource status",
                            "commands": [f"kubectl describe {component.lower()}"],
                            "expected_if_true": "Status conditions that confirm the hypothesis",
                            "expected_if_false": "No status conditions related to the hypothesis"
                        }
                    ],
                    "evidence_needed": ["Logs", "Resource status", "Events"],
                    "conclusion_criteria": "Strong correlation between observed symptoms and hypothesis predictions",
                    "next_steps": [
                        {
                            "description": "Gather more specific information if results are inconclusive",
                            "type": "analysis"
                        }
                    ]
                }
            
            # Add a default empty evidence collection
            if "evidence" not in plan:
                plan["evidence"] = {}
                
            # Add a default conclusion
            if "conclusion" not in plan:
                plan["conclusion"] = {
                    "text": "Investigation in progress",
                    "confidence": 0.0,
                    "confirmed": False
                }
            
            return plan
            
        except Exception as e:
            print(f"Error generating investigation plan: {e}")
            # Return a default plan on error
            return {
                "steps": [
                    {
                        "description": f"Error occurred while generating plan: {str(e)}",
                        "commands": ["Verify LLM API access"],
                        "expected_if_true": "N/A",
                        "expected_if_false": "N/A"
                    }
                ],
                "evidence": {},
                "conclusion": {
                    "text": "Investigation could not be started due to an error",
                    "confidence": 0.0,
                    "confirmed": False
                },
                "next_steps": [
                    {
                        "description": "Try again or select a different hypothesis",
                        "type": "analysis"
                    }
                ]
            }
            
    def execute_investigation_step(self, component: str, finding: Dict[str, Any], hypothesis: Dict[str, Any], step: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an investigation step and return results.
        
        Args:
            component: Component identifier (e.g., "Pod/nginx")
            finding: Finding data for the component
            hypothesis: Hypothesis being investigated
            step: Investigation step to execute
            
        Returns:
            Step results
        """
        step_type = step.get('type', 'command')
        step_desc = step.get('description', 'Unknown step')
        
        result = {
            "step": step,
            "executed": True,
            "timestamp": time.time(),
            "evidence": {},
            "conclusion": None
        }
        
        try:
            if step_type == 'command':
                # Execute a Kubernetes command
                component_type = component.split('/')[0].lower() if '/' in component else 'resource'
                component_name = component.split('/')[1] if '/' in component else component
                
                namespace = 'default'  # Default namespace, could be extracted from the component
                
                # Execute the appropriate command based on the step description
                if 'logs' in step_desc.lower():
                    logs = self.k8s_client.get_pod_logs(component_name, namespace)
                    result["evidence"]["logs"] = logs
                elif 'describe' in step_desc.lower() or 'status' in step_desc.lower():
                    kubectl_result = self._run_kubectl_command(["describe", component_type, component_name, "-n", namespace])
                    result["evidence"]["resource_status"] = kubectl_result.get('output', '')
                elif 'events' in step_desc.lower():
                    events = self.k8s_client.get_events(namespace)
                    filtered_events = [e for e in events if component_name in json.dumps(e)]
                    result["evidence"]["events"] = json.dumps(filtered_events, indent=2)
                else:
                    # Generic command execution
                    commands = step.get('commands', [])
                    command_results = []
                    
                    for cmd in commands:
                        if cmd.startswith('kubectl'):
                            # Execute kubectl command
                            cmd_parts = cmd.split()[1:]  # Remove 'kubectl'
                            kubectl_result = self._run_kubectl_command(cmd_parts)
                            command_results.append({
                                "command": cmd,
                                "output": kubectl_result.get('output', ''),
                                "success": kubectl_result.get('success', False)
                            })
                    
                    if command_results:
                        result["evidence"]["command_results"] = command_results
                
                # Analyze the evidence using LLM to determine next steps or conclusion
                evidence_analysis = self._analyze_investigation_evidence(
                    component, finding, hypothesis, result["evidence"]
                )
                
                # Add the analysis to the result
                result.update(evidence_analysis)
                
            elif step_type == 'analysis':
                # Analyze existing data
                # Get latest evidence from history
                # (This would be more sophisticated in a real implementation)
                evidence_analysis = self._analyze_investigation_evidence(
                    component, finding, hypothesis, {}  # Empty evidence for now
                )
                
                # Add the analysis to the result
                result.update(evidence_analysis)
                
            elif step_type == 'correlation':
                # Correlate findings across components
                # (This would be more sophisticated in a real implementation)
                correlated_components = step.get('components', [])
                
                # Placeholder for correlation analysis
                correlated_findings = []
                
                # Add correlation results
                result["evidence"]["correlation"] = {
                    "components": correlated_components,
                    "findings": correlated_findings
                }
                
                # Analyze the correlations
                evidence_analysis = self._analyze_investigation_evidence(
                    component, finding, hypothesis, result["evidence"]
                )
                
                # Add the analysis to the result
                result.update(evidence_analysis)
                
            else:
                # Unknown step type
                result["error"] = f"Unknown step type: {step_type}"
                
            return result
            
        except Exception as e:
            # Handle errors
            error_msg = str(e)
            print(f"Error executing investigation step: {error_msg}")
            result["error"] = error_msg
            result["executed"] = False
            
            return result
    
    def _analyze_investigation_evidence(self, component: str, finding: Dict[str, Any], hypothesis: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze evidence collected during investigation to determine next steps or conclusion.
        
        Args:
            component: Component identifier
            finding: Finding data
            hypothesis: Hypothesis being investigated
            evidence: Evidence collected
            
        Returns:
            Analysis results
        """
        # Create a prompt for the LLM to analyze the evidence
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to analyze evidence collected during an investigation to determine if it supports
or refutes a specific hypothesis about a Kubernetes issue.

Based on the evidence:
1. Assess whether the hypothesis is supported or refuted
2. Assign a confidence level to your assessment (0.0-1.0)
3. Suggest next steps for further investigation if needed
4. If confident enough, provide a conclusion and recommendations

Think critically about the evidence and consider alternative explanations.
Consider what additional evidence might be needed to increase confidence.

Return a structured analysis in JSON format.
"""
        
        # Construct the user prompt with the component, finding, hypothesis, and evidence details
        component_type = component.split('/')[0] if '/' in component else 'Resource'
        component_name = component.split('/')[1] if '/' in component else component
        
        issue = finding.get('issue', 'Unknown issue')
        hypothesis_desc = hypothesis.get('description', 'Unknown hypothesis')
        
        # Format evidence for the prompt
        evidence_text = ""
        for evidence_type, evidence_data in evidence.items():
            evidence_text += f"\n\n### {evidence_type.capitalize()}\n"
            
            if isinstance(evidence_data, str):
                # Truncate very long evidence to avoid context limits
                if len(evidence_data) > 2000:
                    evidence_text += evidence_data[:2000] + "... [truncated]"
                else:
                    evidence_text += evidence_data
            elif isinstance(evidence_data, list):
                for i, item in enumerate(evidence_data):
                    evidence_text += f"\n{i+1}. {item}"
            elif isinstance(evidence_data, dict):
                for key, value in evidence_data.items():
                    evidence_text += f"\n{key}: {value}"
        
        user_prompt = f"""## Investigation Analysis

**Component:** {component_type}/{component_name}
**Issue:** {issue}
**Hypothesis:** {hypothesis_desc}

### Evidence Collected
{evidence_text if evidence_text else "No evidence has been collected yet."}

Based on this evidence, analyze whether the hypothesis is supported or refuted.
Provide your confidence level, suggested next steps, and a conclusion if possible.

Output your response as a JSON object with the following structure:
{{
  "assessment": "supported/refuted/inconclusive",
  "confidence": 0.7, // Value between 0.0 and 1.0
  "next_steps": [
    {{
      "description": "Specific next step to take",
      "type": "command/analysis/correlation",
      "priority": "high/medium/low"
    }}
  ],
  "conclusion": {{
    "text": "Detailed conclusion about the root cause",
    "confidence": 0.9, // Value between 0.0 and 1.0
    "recommendations": ["Recommendation 1", "Recommendation 2"]
  }}
}}"""

        try:
            # Get analysis from LLM
            result = self.llm_client.analyze(
                context={"problem_description": user_prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Extract the analysis from the result
            analysis = {}
            
            # If there's a final analysis, try to extract JSON from it
            if "final_analysis" in result:
                try:
                    # Try to extract JSON from the text
                    analysis_text = result["final_analysis"]
                    json_start = analysis_text.find("{")
                    json_end = analysis_text.rfind("}") + 1
                    
                    if json_start != -1 and json_end > json_start:
                        json_str = analysis_text[json_start:json_end]
                        analysis = json.loads(json_str)
                except Exception as e:
                    print(f"Error extracting analysis from final analysis: {e}")
            
            # If we couldn't extract a proper analysis, create a default one
            if not analysis:
                analysis = {
                    "assessment": "inconclusive",
                    "confidence": 0.3,
                    "next_steps": [
                        {
                            "description": "Gather more evidence about the issue",
                            "type": "command",
                            "priority": "high"
                        }
                    ]
                }
            
            # Parse the next steps from the analysis
            next_steps = analysis.get("next_steps", [])
            conclusion = analysis.get("conclusion", None)
            
            # Build the result
            result = {
                "analysis": analysis,
                "next_steps": next_steps
            }
            
            # Add conclusion if present
            if conclusion:
                result["conclusion"] = conclusion
            
            return result
            
        except Exception as e:
            print(f"Error analyzing investigation evidence: {e}")
            # Return a default analysis on error
            return {
                "analysis": {
                    "assessment": "error",
                    "confidence": 0.0,
                    "error": str(e)
                },
                "next_steps": [
                    {
                        "description": "Try a different investigation approach",
                        "type": "analysis",
                        "priority": "high"
                    }
                ]
            }
    
    def generate_root_cause_report(self, analysis_history: List[Dict[str, Any]]) -> str:
        """
        Generate a comprehensive root cause analysis report based on the analysis history.
        
        Args:
            analysis_history: List of analysis history entries
            
        Returns:
            Formatted report as a string
        """
        # Create a prompt for the LLM to generate a report
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to generate a comprehensive root cause analysis report based on the investigation history.

The report should include:
1. Executive summary
2. Problem statement and initial symptoms
3. Investigation approach and methodology
4. Key findings and evidence
5. Root cause identification with confidence level
6. Recommendations for resolution
7. Prevention strategies for the future

Use Markdown formatting for the report. Make it clear, concise, and actionable.
Focus on explaining technical concepts in a way that both technical and non-technical audiences can understand.
"""
        
        # Construct the user prompt with the analysis history
        history_text = ""
        
        for i, entry in enumerate(analysis_history):
            stage = entry.get('stage', 'unknown')
            data = entry.get('data', {})
            timestamp = entry.get('timestamp', 0)
            
            history_text += f"\n\n### Step {i+1}: {stage.capitalize()}\n"
            
            if stage == 'initial':
                findings = data.get('findings', [])
                history_text += f"Initial analysis identified {len(findings)} findings."
            elif stage == 'component_selection':
                component = data.get('component', 'Unknown')
                finding = data.get('finding', {})
                history_text += f"Selected component: {component}\n"
                history_text += f"Issue: {finding.get('issue', 'Unknown issue')}"
            elif stage == 'hypothesis_selection':
                hypothesis = data.get('hypothesis', {})
                history_text += f"Selected hypothesis: {hypothesis.get('description', 'Unknown')}\n"
                history_text += f"Confidence: {hypothesis.get('confidence', 0.0)}"
            elif stage == 'investigation_step':
                step = data.get('step', {})
                result = data.get('result', {})
                history_text += f"Investigation step: {step.get('description', 'Unknown')}\n"
                
                evidence = result.get('evidence', {})
                if evidence:
                    history_text += "Evidence collected:\n"
                    for evidence_type, evidence_data in evidence.items():
                        history_text += f"- {evidence_type.capitalize()}: [data available]\n"
            elif stage == 'conclusion':
                conclusion = data.get('conclusion', {})
                history_text += f"Conclusion: {conclusion.get('text', 'Unknown')}\n"
                history_text += f"Confidence: {conclusion.get('confidence', 0.0)}"
        
        user_prompt = f"""## Root Cause Analysis Report Request

I need a comprehensive root cause analysis report based on the following investigation history:

{history_text}

Please generate a well-structured report covering the investigation process, findings, root cause, and recommendations.
Use Markdown formatting for better readability.
"""

        try:
            # Get report from LLM
            result = self.llm_client.analyze(
                context={"problem_description": user_prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            # Extract the report from the result
            if "final_analysis" in result:
                return result["final_analysis"]
            else:
                return "Error generating report: No final analysis available."
            
        except Exception as e:
            print(f"Error generating root cause report: {e}")
            return f"Error generating report: {str(e)}"
            
    def _run_kubectl_command(self, args):
        """
        Run a kubectl command using the K8s client.
        
        Args:
            args: Command arguments (excluding 'kubectl')
            
        Returns:
            Dictionary with command result
        """
        try:
            # Use the k8s_client's _run_kubectl_command if available
            if hasattr(self.k8s_client, '_run_kubectl_command'):
                return self.k8s_client._run_kubectl_command(args)
            else:
                # Fallback to a simple implementation
                import subprocess
                
                cmd = ['kubectl'] + args
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate()
                
                return {
                    'success': process.returncode == 0,
                    'output': stdout.decode('utf-8'),
                    'error': stderr.decode('utf-8')
                }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': str(e)
            }