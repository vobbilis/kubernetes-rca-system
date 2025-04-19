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