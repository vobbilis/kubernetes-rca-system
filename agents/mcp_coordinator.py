from typing import Dict, List, Any, Optional
import uuid
import time
import json
import logging
import networkx as nx
import os
import random

from agents.mcp_metrics_agent import MCPMetricsAgent
from agents.mcp_logs_agent import MCPLogsAgent
from agents.mcp_events_agent import MCPEventsAgent
from agents.mcp_topology_agent import MCPTopologyAgent
from agents.mcp_traces_agent import MCPTracesAgent
from agents.resource_analyzer import ResourceAnalyzer
from utils.llm_client_improved import LLMClient
from utils.logging_helper import EvidenceLogger

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        # Initialize the evidence logger
        self.evidence_logger = EvidenceLogger(logs_dir="logs")
        
        # Store analysis sessions
        self.analyses = {}
    
    def _format_structured_response(self, problematic_pods, pod_statuses, recent_events, namespace):
        """
        Create a well-structured response in JSON format with precise counts and categorization.
        
        Args:
            problematic_pods: List of problematic pod objects
            pod_statuses: Dictionary of pod statuses
            recent_events: List of recent events
            namespace: Namespace being analyzed
            
        Returns:
            Dict with structured response data
        """
        # Prepare the structured response
        total_pods = len(pod_statuses) if pod_statuses else 0
        
        # Create a one-line summary with precise metrics
        summary = f"{len(problematic_pods)} of {total_pods} pods experiencing issues in namespace '{namespace}'"
        
        # Count pods by status for more precise reporting
        status_counts = {}
        restart_counts = {}
        exit_code_counts = {}
        
        # Count by status
        for pod in problematic_pods:
            # Track main status
            status = pod.get("status", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Track containers with restart counts
            for container in pod.get("containers", []):
                restart_count = container.get("restartCount", 0)
                if restart_count > 0:
                    restart_counts[pod.get("name")] = restart_counts.get(pod.get("name"), 0) + restart_count
            
            # Track exit codes
            for container in pod.get("containers", []):
                if container.get("state") and container["state"].get("terminated"):
                    exit_code = container["state"]["terminated"].get("exitCode")
                    if exit_code is not None:
                        exit_code_counts[exit_code] = exit_code_counts.get(exit_code, 0) + 1
        
        # Count events by type
        event_counts = {}
        for event in recent_events:
            reason = event.get("reason", "Unknown")
            event_counts[reason] = event_counts.get(reason, 0) + 1
        
        # Create structured response points
        points = []
        
        # Add status breakdown
        if status_counts:
            status_text = ", ".join([f"{count} {status}" for status, count in status_counts.items()])
            points.append(f"Pod status breakdown: {status_text}")
        
        # Add restart count information
        if restart_counts:
            # Sort by highest restart count
            sorted_restarts = sorted(restart_counts.items(), key=lambda x: x[1], reverse=True)
            restart_text = ", ".join([f"{pod}: {count}" for pod, count in sorted_restarts[:3]])
            if len(sorted_restarts) > 3:
                restart_text += f" and {len(sorted_restarts) - 3} more pods"
            points.append(f"Pod restart counts: {restart_text}")
        
        # Add exit code information
        if exit_code_counts:
            exit_code_text = ", ".join([f"code {code}: {count} occurrences" for code, count in exit_code_counts.items()])
            points.append(f"Container exit codes: {exit_code_text}")
        
        # Add event information
        if event_counts:
            event_text = ", ".join([f"{reason}: {count}" for reason, count in event_counts.items()])
            points.append(f"Recent events by type: {event_text}")
        
        # Create structured sections for the response
        sections = []
        
        # Section for pods with status issues
        if status_counts:
            pod_bullets = []
            for status, count in status_counts.items():
                matching_pods = [p.get("name") for p in problematic_pods if p.get("status") == status]
                matching_pods_str = ", ".join(matching_pods[:3])
                if len(matching_pods) > 3:
                    matching_pods_str += f" and {len(matching_pods) - 3} more"
                pod_bullets.append(f"{count} pods in {status} state: {matching_pods_str}")
            
            sections.append({
                "section_title": "Pod Status Issues",
                "bullets": pod_bullets
            })
        
        # Section for restart issues
        if restart_counts:
            restart_bullets = []
            # Get the top restarting pods
            sorted_restarts = sorted(restart_counts.items(), key=lambda x: x[1], reverse=True)
            for pod_name, count in sorted_restarts[:5]:  # Limit to top 5
                restart_bullets.append(f"{pod_name}: {count} restarts")
            
            sections.append({
                "section_title": "Container Restart Issues",
                "bullets": restart_bullets
            })
        
        # Section for events
        if event_counts:
            event_bullets = []
            for event in recent_events[:5]:  # Limit to 5 most recent events
                reason = event.get("reason", "Unknown")
                message = event.get("message", "No message")
                object_name = event.get("involved_object", "unknown")
                event_bullets.append(f"{reason} on {object_name}: {message}")
            
            sections.append({
                "section_title": "Recent Events",
                "bullets": event_bullets
            })
        
        # Create the complete structured response
        return {
            "response_data": {
                "points": points,
                "sections": sections
            },
            "summary": summary
        }
    
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

        # Get Kubernetes events before analyzing resources
        try:
            events = self.k8s_client.get_events(namespace)
        except Exception as e:
            print(f"Error getting events: {e}")
            events = []
        
        # Run the resource analyzer
        try:
            # Make sure resource analyzer is initialized
            from agents.resource_analyzer import ResourceAnalyzer
            if not hasattr(self, 'resource_analyzer') or self.resource_analyzer is None:
                self.resource_analyzer = ResourceAnalyzer(self.k8s_client)
            
            # Reset findings and reasoning steps to ensure we get fresh results
            self.resource_analyzer.findings = []
            self.resource_analyzer.reasoning_steps = []
            
            # Run analysis
            resource_analysis = self.resource_analyzer.analyze_namespace_resources(namespace)
            
            # Include events in the results
            resource_analysis['events'] = events
            
            # Explicitly include the findings in the results for easier access
            if 'findings' not in resource_analysis and self.resource_analyzer.findings:
                resource_analysis['findings'] = self.resource_analyzer.findings
            
            # Store results
            analysis["results"]["resources"] = resource_analysis
            
            # Debug info
            print(f"Resource analysis found {len(resource_analysis.get('findings', []))} findings")
            print(f"Events captured: {len(events)}")
            
            return resource_analysis
        except Exception as e:
            error_result = {
                "error": f"Resource analysis failed: {str(e)}",
                "findings": [],
                "reasoning_steps": [{
                    "observation": "Error during resource analysis",
                    "conclusion": str(e)
                }],
                "events": events  # Include any events we found
            }
            
            # Store error results
            analysis["results"]["resources"] = error_result
            analysis["status"] = "error"
            
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

RESPONSE FORMAT:
- ALWAYS format your entire response as a bulleted list - do not use paragraphs
- Start each point with a bullet (•) or dash (-) 
- Make your responses concise - no more than 5-7 bullet points total
- For complex issues, use nested bullets with indentation

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
    
    def generate_summary_from_query(self, query: str, namespace: str = "default") -> Dict[str, Any]:
        """
        Generate an investigation summary based on the user's first query.
        
        Args:
            query: The user's initial question or query
            namespace: The Kubernetes namespace being analyzed
            
        Returns:
            Dictionary with the generated summary
        """
        system_prompt = """You are a Kubernetes Root Cause Analysis Expert.
Your task is to generate a clear, concise investigation summary based on the user's initial question.

The summary should:
1. Briefly describe what needs to be investigated based on the user's question
2. Outline the potential areas to be explored in the investigation
3. Mention the specific Kubernetes components that might be relevant
4. Be concise (2-3 sentences) but informative and relevant to the user's question
"""
        
        prompt = f"""## Generate Investigation Summary

Based on the user's initial question about their Kubernetes cluster, generate a concise
investigation summary that outlines what we're trying to accomplish.

### User's Question
"{query}"

### Namespace Being Analyzed
{namespace}

Please provide a clear, concise summary (2-3 sentences) that describes what we're investigating
based on the user's question. The summary will be displayed at the top of the investigation
to remind the user what we're trying to accomplish.
"""
        
        try:
            # Get summary from LLM
            summary_result = self.llm_client.analyze(
                context={"problem_description": prompt},
                tools=[],
                system_prompt=system_prompt
            )
            
            summary = summary_result.get("final_analysis", "")
            
            return {
                "summary": summary,
                "reasoning_steps": summary_result.get("reasoning_steps", [])
            }
            
        except Exception as e:
            # Provide a generic summary in case of an error
            return {
                "summary": f"Investigation of issues in namespace '{namespace}' based on: {query}",
                "error": f"Error generating summary: {str(e)}"
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

RESPONSE FORMAT:
- ALWAYS format your entire response as a bulleted list - do not use paragraphs
- Start each point with a bullet (•) or dash (-) 
- Make your responses concise - no more than 5-7 bullet points total
- For complex issues, use nested bullets with indentation

The summary should cover these areas (all as bullet points):
- Overview: Brief description of the analyzed system and the issues found
- Key Findings: The most significant issues identified across all analysis types
- Root Causes: The underlying problems that are causing the observed issues
- Recommendations: Clear, actionable steps to resolve the issues
- Next Steps: Suggested further investigations if needed
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
        
    def process_user_query(self, query: str, namespace: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user query in natural language and generate a response with suggested next actions.
        
        Args:
            query: User's natural language query
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context (optional)
            
        Returns:
            dict: Response data including text response and suggested actions
        """
        # First, perform a quick analysis to gather current cluster state
        pod_statuses = {}
        problematic_pods = []
        recent_events = []
        
        try:
            # Get pods in the namespace and check their status
            pods = self.k8s_client.get_pods(namespace)
            if pods:
                for pod in pods:
                    pod_name = pod['metadata']['name']
                    pod_phase = pod['status'].get('phase', 'Unknown')
                    pod_statuses[pod_name] = pod_phase
                    
                    # Identify problematic pods
                    if pod_phase != 'Running' and pod_phase != 'Succeeded':
                        container_statuses = []
                        for container in pod['status'].get('containerStatuses', []):
                            if not container.get('ready', False):
                                reason = "Unknown"
                                if 'state' in container:
                                    state_types = container['state'].keys()
                                    if 'waiting' in state_types:
                                        reason = container['state']['waiting'].get('reason', reason)
                                    elif 'terminated' in state_types:
                                        reason = container['state']['terminated'].get('reason', reason)
                                container_statuses.append({
                                    'name': container.get('name', 'unknown'),
                                    'reason': reason
                                })
                        
                        problematic_pods.append({
                            'name': pod_name,
                            'phase': pod_phase,
                            'containers': container_statuses
                        })
            
            # Get recent events
            events = self.k8s_client.get_events(namespace, field_selector="type!=Normal")
            if events:
                for event in events[:5]:  # Get the 5 most recent events
                    recent_events.append({
                        'reason': event.get('reason', 'Unknown'),
                        'message': event.get('message', 'No message'),
                        'involved_object': event.get('involvedObject', {}).get('name', 'Unknown')
                    })
        except Exception as e:
            pass  # Continue even if there's an error in gathering information
        
        # Create a prompt for the LLM with enhanced context
        prompt = f"""
You are an AI assistant specialized in Kubernetes troubleshooting and root cause analysis. 
The user is asking about their Kubernetes cluster, specifically in the namespace '{namespace}'.

User query: {query}

I've already gathered the following information about the cluster to help you respond intelligently:

CLUSTER STATE:
- Total pods in namespace: {len(pod_statuses)}
- Problematic pods (not in 'Running' state): {len(problematic_pods)}
"""

        # Add problematic pod details if any
        if problematic_pods:
            prompt += "\nPROBLEMATIC PODS DETAILS:\n"
            for i, pod in enumerate(problematic_pods, 1):
                prompt += f"{i}. Pod '{pod['name']}' in state '{pod['phase']}'\n"
                for container in pod['containers']:
                    prompt += f"   - Container '{container['name']}': {container['reason']}\n"
        
        # Add recent events if any
        if recent_events:
            prompt += "\nRECENT EVENTS:\n"
            for i, event in enumerate(recent_events, 1):
                prompt += f"{i}. {event['reason']} on {event['involved_object']}: {event['message']}\n"
        
        prompt += """
INSTRUCTIONS:
Even if the user's question is vague or general, please:
1. Identify specific issues based on the cluster state information provided above
2. Provide a ONE-LINE summary of the overall state
3. List all issues with EXACT counts and specific error states, NEVER using qualifiers like "some" or "several"
4. For each problematic resource, specify the exact count and specific error state (e.g., "3 of 10 pods in CrashLoopBackOff")
5. Suggest 3-5 specific next actions the user could take to investigate or resolve identified issues
6. For each action, specify the type of action (run_agent, check_resource, check_logs, check_events, query)

IMPORTANT FORMAT REQUIREMENTS:
- Create a one-line summary that includes the total number of resources and problems
  (e.g., "12 of 24 pods experiencing issues in the default namespace")
- Use a precise numbered/bulleted list for EACH issue type with exact counts and error states
- Make each point specific and data-driven (e.g., "5 pods with CrashLoopBackOff (245+ restarts)" NOT "several pods crashing")
- Include exit codes, event counts, or other specific metrics when available
- Keep technical terms precise and include the exact error messages
- Never use vague quantifiers like "several", "multiple", "some" - always provide exact numbers
- Format all response points as a professional monitoring output focused on precision and clarity

Return your response in JSON format with these fields:
- response_data: An object containing structured response data with:
  - points: Array of strings, each representing a bullet point in your answer
  - sections: An optional array of sections with subsections (use for complex responses):
    - section_title: The title of the section
    - bullets: Array of strings representing bullet points in this section
- summary: A brief 1-2 sentence summary of the issues found or situation
- suggestions: An array of suggestion objects, each with:
  - text: The text to show the user for this suggestion (keep brief but descriptive)
  - action: An object with:
    - type: The action type (run_agent, check_resource, check_logs, check_events, query)
    - [additional fields based on type]
- response: DEPRECATED - only include this for backwards compatibility, with same content as a simple string

Examples of action objects:
- For run_agent: {"type": "run_agent", "agent_type": "logs"}
- For check_resource: {"type": "check_resource", "resource_type": "Pod", "resource_name": "problematic-pod-name"}
- For check_logs: {"type": "check_logs", "pod_name": "problematic-pod-name", "container_name": "main"}
- For check_events: {"type": "check_events", "field_selector": "involvedObject.name=problematic-pod-name"}
- For query: {"type": "query", "query": "Tell me more about CrashLoopBackOff errors"}

FOR GENERAL QUESTIONS:
If the user asked a general question like "what's wrong" or "help me troubleshoot", don't say "I don't understand" - instead identify actual issues from the cluster state and provide specific insight and recommendations.
"""

        # Add full pod listing as additional context
        if pod_statuses:
            prompt += "\nALL PODS IN NAMESPACE:\n"
            for name, status in pod_statuses.items():
                prompt += f"- {name}: {status}\n"
        
        # Get the response from the LLM
        try:
            response_json = self.llm_client.generate_structured_output(prompt)
            
            # Ensure we have the required fields
            if not isinstance(response_json, dict):
                response_json = {}
                
            if "response" not in response_json or not response_json["response"]:
                # Generate a more helpful default response based on cluster state
                default_response = "Based on my analysis of your Kubernetes cluster"
                if problematic_pods:
                    pod_names = ", ".join([pod["name"] for pod in problematic_pods[:3]])
                    if len(problematic_pods) > 3:
                        pod_names += f", and {len(problematic_pods) - 3} more"
                    default_response += f", I've detected {len(problematic_pods)} problematic pods including {pod_names}."
                else:
                    default_response += ", all pods appear to be running normally."
                
                if recent_events:
                    default_response += f" There are also {len(recent_events)} recent warning/error events that may indicate issues."
                
                default_response += " I recommend checking the suggested actions below to investigate further."
                response_json["response"] = default_response
                
            if "summary" not in response_json or not response_json["summary"]:
                # Generate a more precise default summary based on cluster state with specific counts
                if problematic_pods:
                    # Count pods by status for more precision
                    status_counts = {}
                    total_pods = len(pod_statuses) if pod_statuses else 0
                    for pod in problematic_pods:
                        status = pod.get("status", "Unknown")
                        status_counts[status] = status_counts.get(status, 0) + 1
                    
                    # Create a specific summary with exact counts
                    status_summary = ", ".join([f"{count} {status}" for status, count in status_counts.items()])
                    response_json["summary"] = f"{len(problematic_pods)} of {total_pods} pods experiencing issues ({status_summary}) in namespace '{namespace}'."
                else:
                    total_resources = len(pod_statuses) if pod_statuses else 0
                    response_json["summary"] = f"All {total_resources} pods running normally in namespace '{namespace}'."
                
            if "suggestions" not in response_json or not response_json["suggestions"]:
                # Generate smarter default suggestions based on cluster state
                suggestions = []
                
                # Always include comprehensive analysis
                suggestions.append({
                    "text": "Run a comprehensive analysis",
                    "action": {
                        "type": "run_agent",
                        "agent_type": "comprehensive"
                    }
                })
                
                # If there are problematic pods, suggest checking them specifically
                if problematic_pods:
                    for pod in problematic_pods[:2]:  # Limit to first 2 pods to avoid too many suggestions
                        pod_name = pod["name"]
                        suggestions.append({
                            "text": f"Check pod {pod_name}",
                            "action": {
                                "type": "check_resource",
                                "resource_type": "Pod",
                                "resource_name": pod_name
                            }
                        })
                        
                        # Also suggest checking logs for this pod
                        suggestions.append({
                            "text": f"View logs for {pod_name}",
                            "action": {
                                "type": "check_logs",
                                "pod_name": pod_name,
                                "container_name": pod["containers"][0]["name"] if pod["containers"] else None
                            }
                        })
                
                # Add events check if there are recent events
                if recent_events:
                    suggestions.append({
                        "text": "Check recent warning events",
                        "action": {
                            "type": "check_events",
                            "field_selector": "type!=Normal"
                        }
                    })
                
                # If we didn't add any specific suggestions, add the resource analyzer
                if len(suggestions) <= 1:
                    suggestions.append({
                        "text": "Check resource health",
                        "action": {
                            "type": "run_agent",
                            "agent_type": "resources"
                        }
                    })
                
                response_json["suggestions"] = suggestions
            
            return response_json
        except Exception as e:
            # Provide a smarter fallback response based on the cluster state
            default_suggestions = []
            
            # Base suggestion on problematic pods if any with specific counts
            if problematic_pods:
                # Count pods by status for precision
                status_counts = {}
                total_pods = len(pod_statuses) if pod_statuses else 0
                
                for pod in problematic_pods:
                    status = pod.get("status", "Unknown")
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                # Create a specific response with exact counts
                status_details = ", ".join([f"{count} {status}" for status, count in status_counts.items()])
                response_text = f"I found {len(problematic_pods)} of {total_pods} pods with issues: {status_details}"
                
                # Add specific pod suggestions focusing on the most problematic ones first
                # Sort pods by severity (restart count, etc.)
                sorted_pods = sorted(problematic_pods[:4], 
                                    key=lambda p: sum([c.get("restartCount", 0) for c in p.get("containers", [])]), 
                                    reverse=True)
                
                for pod in sorted_pods[:2]:  # Limit to first 2 most problematic pods
                    pod_name = pod["name"]
                    # Add restart count if available
                    restart_count = sum([c.get("restartCount", 0) for c in pod.get("containers", [])])
                    restart_text = f" ({restart_count} restarts)" if restart_count > 0 else ""
                    
                    default_suggestions.append({
                        "text": f"Check pod {pod_name}{restart_text}",
                        "action": {
                            "type": "check_resource",
                            "resource_type": "Pod",
                            "resource_name": pod_name
                        }
                    })
                    
                    # Get the main container name if available
                    container_name = None
                    if pod["containers"]:
                        container_name = pod["containers"][0]["name"]
                    
                    default_suggestions.append({
                        "text": f"View logs for {pod_name}",
                        "action": {
                            "type": "check_logs",
                            "pod_name": pod_name,
                            "container_name": container_name
                        }
                    })
            else:
                response_text = "I couldn't process your question in detail, but I've gathered some information about your cluster"
                
                # Add general suggestions
                default_suggestions.append({
                    "text": "Run a comprehensive analysis",
                    "action": {
                        "type": "run_agent",
                        "agent_type": "comprehensive"
                    }
                })
                
                default_suggestions.append({
                    "text": "Check resource health",
                    "action": {
                        "type": "run_agent",
                        "agent_type": "resources"
                    }
                })
            
            # Always add events check as it's generally useful
            default_suggestions.append({
                "text": "View recent events",
                "action": {
                    "type": "check_events",
                    "field_selector": "type!=Normal"
                }
            })
            
            return {
                "response": f"{response_text}. {str(e)}. Let me suggest some specific actions to help troubleshoot your Kubernetes cluster.",
                "summary": "Automated analysis of cluster state and potential issues",
                "suggestions": default_suggestions
            }
    
    def update_suggestions_after_action(self, previous_suggestions: List[Dict[str, Any]], 
                                        selected_suggestion_index: int,
                                        namespace: str,
                                        context: Optional[str] = None) -> Dict[str, Any]:
        """
        Update the suggested next actions after a user selects one.
        
        Args:
            previous_suggestions: List of previous suggestions
            selected_suggestion_index: Index of the suggestion that was selected
            namespace: Kubernetes namespace being analyzed
            context: Kubernetes context (optional)
            
        Returns:
            dict: Updated response with new suggestions
        """
        if not previous_suggestions or selected_suggestion_index >= len(previous_suggestions):
            # Generate default suggestions if previous ones are invalid
            return {
                "suggestions": [
                    {
                        "text": "Run a comprehensive analysis of your namespace",
                        "action": {
                            "type": "run_agent",
                            "agent_type": "comprehensive"
                        }
                    },
                    {
                        "text": "Check for problematic pods",
                        "action": {
                            "type": "run_agent",
                            "agent_type": "resources"
                        }
                    },
                    {
                        "text": "View recent events",
                        "action": {
                            "type": "check_events",
                            "field_selector": "type!=Normal"
                        }
                    }
                ]
            }
        
        # Get the selected suggestion
        selected_suggestion = previous_suggestions[selected_suggestion_index]
        selected_action = selected_suggestion.get("action", {})
        action_type = selected_action.get("type", "unknown")
        
        # Create a prompt for the LLM to generate new suggestions
        prompt = f"""
Based on the user's selection of the action "{selected_suggestion.get('text', 'unknown action')}" (type: {action_type}), 
please suggest 3-4 new follow-up actions that would be logical next steps in their Kubernetes troubleshooting workflow.

Return your suggestions as a JSON array with these fields for each suggestion:
- text: The text to show the user for this suggestion (be concise but descriptive)
- action: An object with:
  - type: The action type (run_agent, check_resource, check_logs, check_events, query)
  - [additional fields based on type]

Examples of action objects:
- For run_agent: {{"type": "run_agent", "agent_type": "logs"}}
- For check_resource: {{"type": "check_resource", "resource_type": "Pod", "resource_name": "frontend-pod-123"}}
- For check_logs: {{"type": "check_logs", "pod_name": "frontend-pod-123", "container_name": "main"}}
- For check_events: {{"type": "check_events", "field_selector": "involvedObject.name=frontend-pod-123"}}
- For query: {{"type": "query", "query": "What's causing my pod to crash?"}}

Keep these suggestions relevant to what the user has already selected, but diverse enough to explore different troubleshooting paths.
"""
        
        # Add context based on the selected action type
        if action_type == "run_agent":
            agent_type = selected_action.get("agent_type", "unknown")
            prompt += f"\nThe user previously ran an analysis using the {agent_type} agent. Suggest actions that would complement or follow up on this analysis."
            
        elif action_type == "check_resource":
            resource_type = selected_action.get("resource_type", "unknown")
            resource_name = selected_action.get("resource_name", "unknown")
            prompt += f"\nThe user previously checked the {resource_type}/{resource_name} resource. Suggest actions that would help investigate related resources or issues."
            
        elif action_type == "check_logs":
            pod_name = selected_action.get("pod_name", "unknown")
            prompt += f"\nThe user previously checked logs for the pod {pod_name}. Suggest actions that would help understand related issues or components."
            
        elif action_type == "check_events":
            prompt += "\nThe user previously checked Kubernetes events. Suggest actions that would help investigate specific resources mentioned in the events."
        
        # Try to get resource information for more context
        try:
            # Get pods in the namespace
            pods = self.k8s_client.get_pods(namespace)
            if pods:
                problematic_pods = [pod for pod in pods if pod['status'].get('phase') != 'Running']
                if problematic_pods:
                    prompt += "\n\nProblematic pods in the namespace:"
                    for pod in problematic_pods[:3]:  # Limit to 3 problematic pods for context
                        pod_name = pod['metadata']['name']
                        pod_status = pod['status'].get('phase', 'Unknown')
                        prompt += f"\n- {pod_name}: {pod_status}"
                        
                        # Add container statuses if available
                        container_statuses = pod['status'].get('containerStatuses', [])
                        for cs in container_statuses:
                            if not cs.get('ready', False):
                                reason = "Unknown reason"
                                if 'state' in cs:
                                    state_types = cs['state'].keys()
                                    if 'waiting' in state_types:
                                        reason = cs['state']['waiting'].get('reason', reason)
                                    elif 'terminated' in state_types:
                                        reason = cs['state']['terminated'].get('reason', reason)
                                prompt += f"\n  - Container {cs.get('name', 'unknown')}: {reason}"
        except Exception as e:
            pass  # Ignore errors in getting additional context
        
        # Get the response from the LLM
        try:
            response_json = self.llm_client.generate_structured_output(prompt)
            
            # Ensure we have valid suggestions
            if isinstance(response_json, list) and len(response_json) > 0:
                # The LLM returned a direct array of suggestions
                return {"suggestions": response_json}
            elif isinstance(response_json, dict) and "suggestions" in response_json:
                # The LLM returned a dict with a suggestions key
                return response_json
            else:
                # Invalid response format, return default suggestions
                return {
                    "suggestions": [
                        {
                            "text": "Run a comprehensive analysis of your namespace",
                            "action": {
                                "type": "run_agent",
                                "agent_type": "comprehensive"
                            }
                        },
                        {
                            "text": "Check for problematic pods",
                            "action": {
                                "type": "run_agent",
                                "agent_type": "resources"
                            }
                        },
                        {
                            "text": "View recent events",
                            "action": {
                                "type": "check_events",
                                "field_selector": "type!=Normal"
                            }
                        }
                    ]
                }
        except Exception as e:
            # Return default suggestions in case of error
            return {
                "suggestions": [
                    {
                        "text": "Run a comprehensive analysis of your namespace",
                        "action": {
                            "type": "run_agent",
                            "agent_type": "comprehensive"
                        }
                    },
                    {
                        "text": "Check for problematic pods",
                        "action": {
                            "type": "run_agent",
                            "agent_type": "resources"
                        }
                    },
                    {
                        "text": "View recent events",
                        "action": {
                            "type": "check_events",
                            "field_selector": "type!=Normal"
                        }
                    }
                ]
            }
    
    def run_agent_analysis(self, agent_type: str, namespace: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Run an analysis using a specific agent type.
        
        Args:
            agent_type: Type of agent to run ("metrics", "logs", "events", etc.)
            namespace: Kubernetes namespace to analyze
            context: Kubernetes context (optional)
            
        Returns:
            dict: Analysis results
        """
        # Create a configuration for the analysis
        config = {
            "type": agent_type,
            "namespace": namespace,
            "context": context,
            "parameters": {}
        }
        
        # Initialize a new analysis
        analysis_id = self.init_analysis(config)
        
        try:
            # Run the appropriate analysis based on agent type
            if agent_type == "metrics":
                result = self.run_metrics_analysis(analysis_id)
            elif agent_type == "logs":
                result = self.run_logs_analysis(analysis_id)
            elif agent_type == "events":
                result = self.run_events_analysis(analysis_id)
            elif agent_type == "topology":
                result = self.run_topology_analysis(analysis_id)
            elif agent_type == "traces":
                result = self.run_traces_analysis(analysis_id)
            elif agent_type == "resources":
                result = self.run_resource_analysis(analysis_id)
            elif agent_type == "comprehensive":
                result = self._run_comprehensive_analysis(analysis_id, namespace, context)
            else:
                return {"error": f"Unknown agent type: {agent_type}"}
            
            # Generate a summary of the analysis
            summary = self._generate_analysis_summary(agent_type, result)
            result["summary"] = summary
            
            return result
        except Exception as e:
            return {
                "error": str(e),
                "summary": f"An error occurred while running the {agent_type} analysis: {str(e)}"
            }
    
    def analyze_resource(self, resource_type: str, resource_name: str, resource_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a specific Kubernetes resource.
        
        Args:
            resource_type: Type of resource (Pod, Deployment, Service, etc.)
            resource_name: Name of the resource
            resource_details: Resource data
            
        Returns:
            dict: Analysis results with summary
        """
        # Create a prompt for the LLM to analyze the resource
        prompt = f"""
Analyze the following Kubernetes {resource_type} resource named {resource_name}.

Resource details:
```yaml
{json.dumps(resource_details, indent=2)}
```

Please provide:
1. A summary of the resource's current state and any issues you identify
2. Potential causes for any problems detected
3. Recommended actions to resolve any issues

Return your analysis in JSON format with these fields:
- summary: A brief summary of the resource's state and any issues
- issues: An array of identified issues, each with:
  - description: Description of the issue
  - severity: (critical, high, medium, low, info)
- recommendations: An array of recommended actions
"""
        
        # Try to get the analysis from the LLM
        try:
            analysis = self.llm_client.generate_structured_output(prompt)
            
            # Ensure we have the required fields
            if not isinstance(analysis, dict):
                analysis = {}
                
            if "summary" not in analysis:
                analysis["summary"] = f"Analysis of {resource_type}/{resource_name} completed."
                
            if "issues" not in analysis:
                analysis["issues"] = []
                
            if "recommendations" not in analysis:
                analysis["recommendations"] = []
                
            return analysis
        except Exception as e:
            return {
                "error": str(e),
                "summary": f"Failed to analyze {resource_type}/{resource_name}: {str(e)}"
            }
    
    def analyze_logs(self, pod_name: str, container_name: Optional[str], logs: str) -> Dict[str, Any]:
        """
        Analyze logs from a pod or container.
        
        Args:
            pod_name: Name of the pod
            container_name: Name of the container (optional)
            logs: Log content
            
        Returns:
            dict: Analysis results with summary
        """
        # Create a prompt for the LLM to analyze the logs
        container_info = f" (container: {container_name})" if container_name else ""
        prompt = f"""
Analyze the following logs from pod {pod_name}{container_info}.

```
{logs[:5000]}  # Limit logs to first 5000 characters
```

Please provide:
1. A summary of any issues or patterns you identify in the logs
2. Potential error messages or warnings
3. Recommended actions to resolve any issues

Return your analysis in JSON format with these fields:
- summary: A brief summary of the log analysis
- errors: An array of identified errors, each with:
  - message: The error message
  - count: How many times it appears (estimate)
  - severity: (critical, high, medium, low, info)
- patterns: Any patterns or trends identified
- recommendations: An array of recommended actions
"""
        
        # Try to get the analysis from the LLM
        try:
            analysis = self.llm_client.generate_structured_output(prompt)
            
            # Ensure we have the required fields
            if not isinstance(analysis, dict):
                analysis = {}
                
            if "summary" not in analysis:
                analysis["summary"] = f"Analysis of logs from {pod_name}{container_info} completed."
                
            if "errors" not in analysis:
                analysis["errors"] = []
                
            if "patterns" not in analysis:
                analysis["patterns"] = []
                
            if "recommendations" not in analysis:
                analysis["recommendations"] = []
                
            return analysis
        except Exception as e:
            return {
                "error": str(e),
                "summary": f"Failed to analyze logs from {pod_name}{container_info}: {str(e)}"
            }
    
    def analyze_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze Kubernetes events.
        
        Args:
            events: List of Kubernetes events
            
        Returns:
            dict: Analysis results with summary
        """
        # Create a prompt for the LLM to analyze the events
        prompt = f"""
Analyze the following Kubernetes events.

Events:
```yaml
{json.dumps(events[:20], indent=2)}  # Limit to first 20 events
```

Please provide:
1. A summary of the events and any issues they indicate
2. Patterns or trends across multiple events
3. Recommended actions to address any issues

Return your analysis in JSON format with these fields:
- summary: A brief summary of the events analysis
- issues: An array of identified issues, each with:
  - description: Description of the issue
  - severity: (critical, high, medium, low, info)
  - affected_resources: Array of affected resources
- patterns: Any patterns or trends identified
- recommendations: An array of recommended actions
"""
        
        # Try to get the analysis from the LLM
        try:
            analysis = self.llm_client.generate_structured_output(prompt)
            
            # Ensure we have the required fields
            if not isinstance(analysis, dict):
                analysis = {}
                
            if "summary" not in analysis:
                analysis["summary"] = "Analysis of Kubernetes events completed."
                
            if "issues" not in analysis:
                analysis["issues"] = []
                
            if "patterns" not in analysis:
                analysis["patterns"] = []
                
            if "recommendations" not in analysis:
                analysis["recommendations"] = []
                
            return analysis
        except Exception as e:
            return {
                "error": str(e),
                "summary": f"Failed to analyze Kubernetes events: {str(e)}"
            }
    
    def _generate_analysis_summary(self, agent_type: str, result: Dict[str, Any]) -> str:
        """
        Generate a summary of an analysis result.
        
        Args:
            agent_type: Type of agent that performed the analysis
            result: Analysis results
            
        Returns:
            str: Summary text
        """
        # Create a prompt for the LLM to summarize the analysis
        prompt = f"""
Summarize the results of a Kubernetes {agent_type} analysis.

Analysis results:
```json
{json.dumps(result, indent=2)}
```

Please provide a concise summary (2-3 sentences) of the key findings and issues identified.
"""
        
        # Try to get the summary from the LLM
        try:
            summary = self.llm_client.generate_completion(prompt)
            return summary
        except Exception as e:
            return f"Analysis of {agent_type} completed. {len(result.get('findings', []))} issues found."
            
    def get_resource_details(self, resource_type: str, resource_name: str, namespace: str) -> Dict[str, Any]:
        """
        Get detailed information about a Kubernetes resource.
        
        Args:
            resource_type: Type of resource (Pod, Deployment, Service, etc.)
            resource_name: Name of the resource
            namespace: Namespace of the resource
            
        Returns:
            dict: Resource details
        """
        if resource_type.lower() == "pod":
            return self.k8s_client.get_pod(namespace, resource_name) or {}
        elif resource_type.lower() == "deployment":
            # This requires implementation in the K8sClient class
            # This is a placeholder until implemented
            return {}
        elif resource_type.lower() == "service":
            # This requires implementation in the K8sClient class
            # This is a placeholder until implemented
            return {}
        else:
            return {}
    
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
            
            # Log each hypothesis with evidence
            for hypothesis in hypotheses:
                # Gather evidence for this component
                evidence = self._get_evidence_for_component(component)
                
                # Log the hypothesis with evidence
                log_path = self.evidence_logger.log_hypothesis(
                    component=component,
                    finding=finding,
                    hypothesis=hypothesis,
                    evidence=evidence
                )
                
                # Add a reference to the logged evidence
                hypothesis['evidence_log'] = log_path
                logger.info(f"Logged hypothesis evidence for '{hypothesis.get('description', 'unknown')}' to {log_path}")
            
            return hypotheses
            
        except Exception as e:
            logger.error(f"Error generating hypotheses: {e}")
            # Create default hypothesis on error
            error_hypothesis = {
                "description": f"Error occurred while analyzing {component}: {str(e)}",
                "confidence": 0.3,
                "investigation_steps": [
                    "Check system connectivity",
                    "Verify LLM API access",
                    "Try again with more specific information"
                ],
                "related_components": []
            }
            
            # Log the error hypothesis
            log_path = self.evidence_logger.log_hypothesis(
                component=component,
                finding=finding,
                hypothesis=error_hypothesis,
                evidence={"error": str(e)}
            )
            
            error_hypothesis['evidence_log'] = log_path
            
            return [error_hypothesis]
    
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
                
                # Log the evidence collected in this step
                try:
                    log_path = self.evidence_logger.log_investigation_step(
                        component=component,
                        hypothesis=hypothesis,
                        step=step,
                        result=result
                    )
                    result["evidence_log"] = log_path
                    logger.info(f"Logged investigation step evidence to {log_path}")
                except Exception as e:
                    logger.error(f"Failed to log investigation step evidence: {e}")
                
                # Add the analysis to the result
                result.update(evidence_analysis)
                
            elif step_type == 'analysis':
                # Analyze existing data
                # Get latest evidence from history
                # (This would be more sophisticated in a real implementation)
                evidence_analysis = self._analyze_investigation_evidence(
                    component, finding, hypothesis, {}  # Empty evidence for now
                )
                
                # Log the analysis step
                try:
                    log_path = self.evidence_logger.log_investigation_step(
                        component=component,
                        hypothesis=hypothesis,
                        step=step,
                        result=result
                    )
                    result["evidence_log"] = log_path
                    logger.info(f"Logged analysis step to {log_path}")
                except Exception as e:
                    logger.error(f"Failed to log analysis step: {e}")
                
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
                
                # Log the correlation step
                try:
                    log_path = self.evidence_logger.log_investigation_step(
                        component=component,
                        hypothesis=hypothesis,
                        step=step,
                        result=result
                    )
                    result["evidence_log"] = log_path
                    logger.info(f"Logged correlation step to {log_path}")
                except Exception as e:
                    logger.error(f"Failed to log correlation step: {e}")
                
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
    
    def _get_evidence_for_component(self, component: str) -> Dict[str, Any]:
        """
        Gather evidence for a specific component.
        
        Args:
            component: The Kubernetes component identifier (e.g., "Pod/nginx")
            
        Returns:
            Dictionary with evidence
        """
        evidence = {}
        
        # Parse component type and name
        try:
            comp_type, comp_name = component.split('/', 1)
        except Exception as e:
            logger.error(f"Could not parse component: {component}, error: {e}")
            return {"error": f"Could not parse component: {component}"}
        
        # Get namespace from current analysis or use default
        namespace = "default"
        for analysis_id, analysis in self.analyses.items():
            if analysis["status"] != "failed":
                namespace = analysis["config"].get("namespace", "default")
                break
        
        # Collect evidence based on component type
        try:
            if comp_type.lower() == "pod":
                # Get pod details
                try:
                    pod = self.k8s_client.get_pod(namespace, comp_name)
                    evidence["pod_details"] = pod
                except Exception as e:
                    evidence["pod_details_error"] = str(e)
                
                # Get pod logs
                try:
                    pod_logs = self.k8s_client.get_pod_logs(namespace, comp_name, tail_lines=100)
                    evidence["pod_logs"] = pod_logs
                except Exception as e:
                    evidence["pod_logs_error"] = str(e)
                
                # Get pod events
                try:
                    pod_events = self.k8s_client.get_events(namespace=namespace, field_selector=f"involvedObject.name={comp_name}")
                    evidence["pod_events"] = pod_events
                except Exception as e:
                    evidence["pod_events_error"] = str(e)
                
            elif comp_type.lower() == "deployment":
                # Get deployment details
                try:
                    deployment = self.k8s_client.get_deployment(namespace, comp_name)
                    evidence["deployment_details"] = deployment
                except Exception as e:
                    evidence["deployment_details_error"] = str(e)
                
                # Get deployment events
                try:
                    deployment_events = self.k8s_client.get_events(namespace=namespace, field_selector=f"involvedObject.name={comp_name}")
                    evidence["deployment_events"] = deployment_events
                except Exception as e:
                    evidence["deployment_events_error"] = str(e)
                
                # Get pods for this deployment
                try:
                    pods = self.k8s_client.get_pods(namespace)
                    # Filter pods belonging to this deployment
                    deployment_pods = []
                    for pod in pods:
                        for owner_ref in pod.get("metadata", {}).get("ownerReferences", []):
                            if owner_ref.get("name") == comp_name:
                                deployment_pods.append(pod)
                    
                    evidence["deployment_pods"] = deployment_pods
                    
                    # Get logs from one of the pods (if any)
                    if deployment_pods:
                        sample_pod = deployment_pods[0]["metadata"]["name"]
                        pod_logs = self.k8s_client.get_pod_logs(namespace, sample_pod, tail_lines=100)
                        evidence["sample_pod_logs"] = pod_logs
                except Exception as e:
                    evidence["deployment_pods_error"] = str(e)
                
            elif comp_type.lower() == "service":
                # Get service details
                try:
                    service = self.k8s_client.get_service(namespace, comp_name)
                    evidence["service_details"] = service
                except Exception as e:
                    evidence["service_details_error"] = str(e)
                
                # Get service events
                try:
                    service_events = self.k8s_client.get_events(namespace=namespace, field_selector=f"involvedObject.name={comp_name}")
                    evidence["service_events"] = service_events
                except Exception as e:
                    evidence["service_events_error"] = str(e)
                
                # Get endpoints for this service
                try:
                    endpoints = self.k8s_client.get_endpoints(namespace, comp_name)
                    evidence["service_endpoints"] = endpoints
                except Exception as e:
                    evidence["service_endpoints_error"] = str(e)
            
            # Add more component types as needed
            elif comp_type.lower() == "persistentvolumeclaim" or comp_type.lower() == "pvc":
                # Get PVC details
                try:
                    pvc = self.k8s_client.get_pvc(namespace, comp_name)
                    evidence["pvc_details"] = pvc
                except Exception as e:
                    evidence["pvc_details_error"] = str(e)
                
                # Get PVC events
                try:
                    pvc_events = self.k8s_client.get_events(namespace=namespace, field_selector=f"involvedObject.name={comp_name}")
                    evidence["pvc_events"] = pvc_events
                except Exception as e:
                    evidence["pvc_events_error"] = str(e)
            
            else:
                # Generic resource - get basic details and events
                try:
                    # Use kubectl command for generic resources
                    kubectl_result = self._run_kubectl_command(["get", comp_type.lower(), comp_name, "-n", namespace, "-o", "json"])
                    if kubectl_result.get("success", False):
                        try:
                            resource_details = json.loads(kubectl_result.get("output", "{}"))
                            evidence["resource_details"] = resource_details
                        except:
                            evidence["resource_details"] = kubectl_result.get("output", "")
                    
                    # Get events
                    try:
                        resource_events = self.k8s_client.get_events(namespace=namespace, field_selector=f"involvedObject.name={comp_name}")
                        evidence["resource_events"] = resource_events
                    except Exception as e:
                        evidence["resource_events_error"] = str(e)
                    
                except Exception as e:
                    evidence["resource_error"] = str(e)
            
            # Add cluster-wide information that might be relevant
            try:
                # Get nodes info (simplified for context)
                node_status = {}
                nodes = self.k8s_client.get_nodes()
                for node in nodes:
                    name = node.get("metadata", {}).get("name", "unknown")
                    conditions = node.get("status", {}).get("conditions", [])
                    ready_condition = next((c for c in conditions if c.get("type") == "Ready"), {})
                    node_status[name] = {
                        "ready": ready_condition.get("status") == "True",
                        "lastTransitionTime": ready_condition.get("lastTransitionTime")
                    }
                
                evidence["cluster_node_status"] = node_status
            except Exception as e:
                evidence["cluster_info_error"] = str(e)
                
        except Exception as e:
            logger.error(f"Error collecting evidence for {component}: {e}")
            evidence["error"] = str(e)
        
        return evidence
        
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