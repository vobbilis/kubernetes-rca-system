import os
import json
import sys
import logging
from typing import Dict, List, Any, Optional, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from anthropic import Anthropic
from anthropic.types import Message

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMClient:
    """
    Client for interacting with large language models.
    Currently supports OpenAI and Anthropic APIs.
    
    This client abstracts the differences between the APIs and provides a unified
    interface for generating completions and analyzing Kubernetes data.
    """
    
    def __init__(self, provider="openai"):
        """
        Initialize the LLM client with the specified provider.
        
        Args:
            provider: LLM provider to use ("openai" or "anthropic")
        """
        self.provider = provider.lower()
        
        if self.provider == "openai":
            # Check OpenAI API key
            openai_api_key = os.environ.get("OPENAI_API_KEY")
            if not openai_api_key:
                logger.error("OPENAI_API_KEY environment variable not set. Please set it to use OpenAI models.")
                sys.exit("OPENAI_API_KEY environment variable not set")
            
            self.openai_client = OpenAI(api_key=openai_api_key)
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            self.default_model = "gpt-4o"
        
        elif self.provider == "anthropic":
            # Check Anthropic API key
            anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not anthropic_api_key:
                logger.error("ANTHROPIC_API_KEY environment variable not set. Please set it to use Anthropic models.")
                sys.exit("ANTHROPIC_API_KEY environment variable not set")
            
            self.anthropic_client = Anthropic(api_key=anthropic_api_key)
            # the newest Anthropic model is "claude-3-5-sonnet-20241022" which was released October 22, 2024
            # do not change this unless explicitly requested by the user
            self.default_model = "claude-3-5-sonnet-20241022"
        
        else:
            logger.error(f"Unknown provider: {provider}")
            sys.exit(f"Unknown provider: {provider}. Only 'openai' and 'anthropic' are supported.")
    
    def generate_completion(self, prompt: Union[str, List[Dict]], 
                           model: Optional[str] = None,
                           temperature: float = 0.2,
                           max_tokens: int = 2000) -> str:
        """
        Generate a completion for the given prompt.
        
        Args:
            prompt: Prompt text or chat messages
            model: Model name to use (if None, use the default model)
            temperature: Sampling temperature
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated completion text
        """
        if model is None:
            model = self.default_model
        
        if self.provider == "openai":
            # Handle different prompt types
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = prompt
            
            try:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                return response.choices[0].message.content
            
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                return f"Error generating completion: {e}"
        
        elif self.provider == "anthropic":
            # Handle different prompt types
            if isinstance(prompt, str):
                system_content = "You are a Kubernetes expert analyzing cluster data for root cause analysis."
                user_content = prompt
                
                try:
                    response = self.anthropic_client.messages.create(
                        model=model,
                        system=system_content,
                        messages=[{"role": "user", "content": user_content}],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    return response.content[0].text
                
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    return f"Error generating completion: {e}"
            
            else:
                # Handle chat history format
                system_content = "You are a Kubernetes expert analyzing cluster data for root cause analysis."
                
                # Convert OpenAI-style messages to Anthropic format
                messages = []
                
                for msg in prompt:
                    if msg["role"] == "system":
                        system_content = msg["content"]
                    else:
                        messages.append({"role": msg["role"], "content": msg["content"]})
                
                try:
                    response = self.anthropic_client.messages.create(
                        model=model,
                        system=system_content,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    return response.content[0].text
                
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    return f"Error generating completion: {e}"
    
    def analyze_pods(self, pods_data: List[Dict], namespace: str) -> Dict[str, Any]:
        """
        Analyze pods data for issues.
        
        Args:
            pods_data: List of pod dictionaries
            namespace: Namespace of the pods
            
        Returns:
            Dictionary with analysis results
        """
        if not pods_data:
            return {"error": "No pod data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": f"""
            You are a Kubernetes expert analyzing pod data for root cause analysis.
            Identify any issues with the pods in the '{namespace}' namespace.
            Focus on:
            1. Pods that are not Running or not Ready
            2. Pods with high restart counts
            3. Container state issues (waiting, terminated)
            4. Initialization failures
            5. Probe failures
            
            Your response should be in JSON format with the following structure:
            {{
                "issues": [
                    {{
                        "pod_name": "name-of-pod",
                        "severity": "high|medium|low",
                        "issue_type": "restart|pending|crash|probe-failure|etc",
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }}
                ],
                "summary": "brief summary of the overall pod health in this namespace"
            }}
            
            If no issues are found, return an empty issues array but still include a summary.
            """
        }
        
        user_message = {
            "role": "user",
            "content": f"Here's the pod data for namespace '{namespace}':\n\n{json.dumps(pods_data, indent=2)}\n\nPlease analyze for issues."
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def analyze_metrics(self, 
                        pod_metrics: Dict[str, Dict], 
                        node_metrics: Dict[str, Dict] = None,
                        pods_data: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze metrics data for issues.
        
        Args:
            pod_metrics: Dictionary of pod metrics data
            node_metrics: Dictionary of node metrics data (optional)
            pods_data: List of pod dictionaries for reference (optional)
            
        Returns:
            Dictionary with analysis results
        """
        if not pod_metrics and not node_metrics:
            return {"error": "No metrics data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes metrics expert analyzing resource usage data for root cause analysis.
            Identify any issues with resource usage in the provided metrics.
            Focus on:
            1. High CPU usage (>80% is concerning)
            2. High memory usage (>80% is concerning)
            3. Resource saturation at the node level
            4. Pods approaching their resource limits
            5. Imbalances in resource consumption across pods/nodes
            
            Your response should be in JSON format with the following structure:
            {
                "pod_issues": [
                    {
                        "pod_name": "name-of-pod",
                        "severity": "high|medium|low",
                        "resource_type": "cpu|memory",
                        "usage_percentage": 85,
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "node_issues": [
                    {
                        "node_name": "name-of-node",
                        "severity": "high|medium|low",
                        "resource_type": "cpu|memory",
                        "usage_percentage": 90,
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "summary": "brief summary of the overall resource usage situation"
            }
            
            If no issues are found, return empty arrays but still include a summary.
            """
        }
        
        user_message_content = "Here's the metrics data for analysis:\n\n"
        
        if pod_metrics:
            user_message_content += f"Pod Metrics:\n{json.dumps(pod_metrics, indent=2)}\n\n"
        
        if node_metrics:
            user_message_content += f"Node Metrics:\n{json.dumps(node_metrics, indent=2)}\n\n"
        
        if pods_data:
            user_message_content += f"Pod Details:\n{json.dumps(pods_data, indent=2)}\n\n"
        
        user_message_content += "Please analyze for resource usage issues."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def analyze_logs(self, 
                     logs_data: Dict[str, str], 
                     pods_data: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze pod logs for issues.
        
        Args:
            logs_data: Dictionary mapping pod names to their logs
            pods_data: List of pod dictionaries for reference (optional)
            
        Returns:
            Dictionary with analysis results
        """
        if not logs_data:
            return {"error": "No logs data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes logs expert analyzing container logs for root cause analysis.
            Identify any issues, errors, or anomalies in the provided logs.
            Focus on:
            1. Error messages
            2. Stack traces
            3. Warnings about resource usage
            4. Application errors
            5. Connectivity issues
            6. Timeout errors
            
            Your response should be in JSON format with the following structure:
            {
                "log_issues": [
                    {
                        "pod_name": "name-of-pod",
                        "severity": "high|medium|low",
                        "issue_type": "application-error|system-error|warning|connectivity",
                        "log_snippet": "relevant part of the log",
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "summary": "brief summary of the overall log analysis"
            }
            
            If no issues are found, return an empty log_issues array but still include a summary.
            """
        }
        
        # Prepare logs for the prompt (truncate if necessary to fit into context window)
        truncated_logs = {}
        max_log_length = 5000  # Characters per log
        
        for pod_name, log_content in logs_data.items():
            if len(log_content) > max_log_length:
                truncated_logs[pod_name] = log_content[:max_log_length] + "\n...[truncated]..."
            else:
                truncated_logs[pod_name] = log_content
        
        user_message_content = "Here's the log data for analysis:\n\n"
        
        for pod_name, log_content in truncated_logs.items():
            user_message_content += f"Logs for pod '{pod_name}':\n```\n{log_content}\n```\n\n"
        
        if pods_data:
            user_message_content += f"Pod Details:\n{json.dumps(pods_data, indent=2)}\n\n"
        
        user_message_content += "Please analyze for issues in the logs."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def analyze_events(self, 
                       events_data: List[Dict], 
                       pods_data: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze Kubernetes events for issues.
        
        Args:
            events_data: List of event dictionaries
            pods_data: List of pod dictionaries for reference (optional)
            
        Returns:
            Dictionary with analysis results
        """
        if not events_data:
            return {"error": "No events data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes events expert analyzing cluster events for root cause analysis.
            Identify any issues or anomalies in the provided events.
            Focus on:
            1. Warning or Error events
            2. Events with high counts
            3. Repeated failures
            4. Resources being throttled
            5. Scheduling issues
            
            Your response should be in JSON format with the following structure:
            {
                "event_issues": [
                    {
                        "involved_object": {
                            "kind": "Pod|Deployment|etc",
                            "name": "name-of-object"
                        },
                        "severity": "high|medium|low",
                        "reason": "event reason",
                        "count": 5,
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "summary": "brief summary of the overall event analysis"
            }
            
            If no issues are found, return an empty event_issues array but still include a summary.
            """
        }
        
        user_message_content = "Here's the events data for analysis:\n\n"
        user_message_content += f"Events:\n{json.dumps(events_data, indent=2)}\n\n"
        
        if pods_data:
            user_message_content += f"Pod Details:\n{json.dumps(pods_data, indent=2)}\n\n"
        
        user_message_content += "Please analyze for issues in the events."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def analyze_topology(self, 
                         services: List[Dict], 
                         pods: List[Dict], 
                         deployments: List[Dict],
                         network_policies: List[Dict] = None,
                         ingresses: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze the topology of a Kubernetes namespace.
        
        Args:
            services: List of service dictionaries
            pods: List of pod dictionaries
            deployments: List of deployment dictionaries
            network_policies: List of network policy dictionaries (optional)
            ingresses: List of ingress dictionaries (optional)
            
        Returns:
            Dictionary with analysis results
        """
        if not services and not pods and not deployments:
            return {"error": "No topology data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes network and topology expert analyzing cluster resources for root cause analysis.
            Identify any issues, misconfigurations, or potential problems in the provided topology data.
            Focus on:
            1. Service-to-pod mapping issues (selectors not matching labels)
            2. Network policy concerns (overly restrictive policies)
            3. Ingress configuration issues
            4. Deployment scaling or rollout problems
            5. Service exposure and accessibility
            
            Your response should be in JSON format with the following structure:
            {
                "topology_issues": [
                    {
                        "resource_type": "Service|Pod|Deployment|NetworkPolicy|Ingress",
                        "resource_name": "name-of-resource",
                        "severity": "high|medium|low",
                        "issue_type": "selector-mismatch|network-isolation|scaling-issue|etc",
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "service_connections": [
                    {
                        "service": "service-name",
                        "selects_pods": ["pod1", "pod2"],
                        "potential_issues": "description of any selector issues or null if none"
                    }
                ],
                "network_restrictions": [
                    {
                        "source": "resource-name",
                        "destination": "resource-name",
                        "is_blocked": true,
                        "blocking_policy": "policy-name or null if none",
                        "impact": "description of the impact of this restriction"
                    }
                ],
                "summary": "brief summary of the overall topology analysis"
            }
            
            If no issues are found, return appropriate empty arrays but still include a summary.
            """
        }
        
        user_message_content = "Here's the topology data for analysis:\n\n"
        
        if services:
            user_message_content += f"Services:\n{json.dumps(services, indent=2)}\n\n"
        
        if pods:
            user_message_content += f"Pods:\n{json.dumps(pods, indent=2)}\n\n"
        
        if deployments:
            user_message_content += f"Deployments:\n{json.dumps(deployments, indent=2)}\n\n"
        
        if network_policies:
            user_message_content += f"Network Policies:\n{json.dumps(network_policies, indent=2)}\n\n"
        
        if ingresses:
            user_message_content += f"Ingresses:\n{json.dumps(ingresses, indent=2)}\n\n"
        
        user_message_content += "Please analyze for topology and network issues."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def analyze_traces(self, 
                       trace_data: Dict[str, Any],
                       service_dependencies: Dict[str, List[str]] = None,
                       error_rates: Dict[str, float] = None,
                       latency_stats: Dict[str, Dict] = None) -> Dict[str, Any]:
        """
        Analyze distributed traces for issues.
        
        Args:
            trace_data: Dictionary with trace details
            service_dependencies: Dictionary of service dependencies (optional)
            error_rates: Dictionary of service error rates (optional)
            latency_stats: Dictionary of service latency statistics (optional)
            
        Returns:
            Dictionary with analysis results
        """
        if not trace_data:
            return {"error": "No trace data available for analysis"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a distributed tracing expert analyzing trace data for Kubernetes microservices.
            Identify any issues, bottlenecks, or anomalies in the provided trace data.
            Focus on:
            1. High latency spans
            2. Error spans
            3. Bottleneck services
            4. Unusual dependencies
            5. Service communication issues
            
            Your response should be in JSON format with the following structure:
            {
                "trace_issues": [
                    {
                        "service": "service-name",
                        "operation": "operation-name",
                        "severity": "high|medium|low",
                        "issue_type": "latency|error|bottleneck|etc",
                        "duration_ms": 1500,
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "service_issues": [
                    {
                        "service": "service-name",
                        "severity": "high|medium|low", 
                        "issue_type": "high-error-rate|high-latency|bottleneck|etc",
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "dependency_issues": [
                    {
                        "source_service": "service-name",
                        "target_service": "service-name",
                        "severity": "high|medium|low",
                        "issue_type": "latency|error|bottleneck|etc",
                        "description": "detailed description of the issue",
                        "potential_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"]
                    }
                ],
                "summary": "brief summary of the overall trace analysis"
            }
            
            If no issues are found, return appropriate empty arrays but still include a summary.
            """
        }
        
        user_message_content = "Here's the trace data for analysis:\n\n"
        user_message_content += f"Trace Details:\n{json.dumps(trace_data, indent=2)}\n\n"
        
        if service_dependencies:
            user_message_content += f"Service Dependencies:\n{json.dumps(service_dependencies, indent=2)}\n\n"
        
        if error_rates:
            user_message_content += f"Error Rates by Service:\n{json.dumps(error_rates, indent=2)}\n\n"
        
        if latency_stats:
            user_message_content += f"Latency Statistics by Service:\n{json.dumps(latency_stats, indent=2)}\n\n"
        
        user_message_content += "Please analyze for issues in the traces."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def correlate_findings(self,
                          metrics_analysis: Dict[str, Any] = None,
                          logs_analysis: Dict[str, Any] = None,
                          events_analysis: Dict[str, Any] = None,
                          topology_analysis: Dict[str, Any] = None,
                          traces_analysis: Dict[str, Any] = None,
                          problem_description: str = None) -> Dict[str, Any]:
        """
        Correlate findings from different analyses to identify related issues.
        
        Args:
            metrics_analysis: Results from metrics analysis (optional)
            logs_analysis: Results from logs analysis (optional)
            events_analysis: Results from events analysis (optional)
            topology_analysis: Results from topology analysis (optional)
            traces_analysis: Results from traces analysis (optional)
            problem_description: User-provided description of the problem (optional)
            
        Returns:
            Dictionary with correlated findings
        """
        if not any([metrics_analysis, logs_analysis, events_analysis, topology_analysis, traces_analysis]):
            return {"error": "No analysis data available for correlation"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes expert correlating findings from multiple analyses to perform root cause analysis.
            Examine the results from different analyses to identify patterns, relationships, and root causes of issues.
            Focus on:
            1. Common symptoms across different signals
            2. Cause-effect relationships
            3. Issue propagation across services
            4. Root causes vs. downstream effects
            5. Prioritization of issues by impact
            
            Your response should be in JSON format with the following structure:
            {
                "correlated_issues": [
                    {
                        "issue_id": "unique-id",
                        "title": "Brief title of the correlated issue",
                        "severity": "critical|high|medium|low",
                        "affected_components": ["component1", "component2"],
                        "signals": ["metrics", "logs", "events", "topology", "traces"],
                        "description": "Detailed description of the correlated issue",
                        "root_causes": ["cause1", "cause2"],
                        "recommendations": ["recommendation1", "recommendation2"],
                        "supporting_evidence": [
                            "Evidence from metrics: description",
                            "Evidence from logs: description"
                        ]
                    }
                ],
                "root_cause_analysis": {
                    "primary_issues": ["issue_id1", "issue_id2"],
                    "secondary_issues": ["issue_id3", "issue_id4"],
                    "explanation": "Overall explanation of what's happening in the system"
                },
                "summary": "brief summary of the overall root cause analysis"
            }
            """
        }
        
        user_message_content = "Here are the analysis results for correlation:\n\n"
        
        if problem_description:
            user_message_content += f"Problem Description: {problem_description}\n\n"
        
        if metrics_analysis:
            user_message_content += f"Metrics Analysis:\n{json.dumps(metrics_analysis, indent=2)}\n\n"
        
        if logs_analysis:
            user_message_content += f"Logs Analysis:\n{json.dumps(logs_analysis, indent=2)}\n\n"
        
        if events_analysis:
            user_message_content += f"Events Analysis:\n{json.dumps(events_analysis, indent=2)}\n\n"
        
        if topology_analysis:
            user_message_content += f"Topology Analysis:\n{json.dumps(topology_analysis, indent=2)}\n\n"
        
        if traces_analysis:
            user_message_content += f"Traces Analysis:\n{json.dumps(traces_analysis, indent=2)}\n\n"
        
        user_message_content += "Please correlate these findings to identify root causes and relationships between issues."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the analysis
        analysis_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.1,
            max_tokens=3000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = analysis_text.find("{")
            json_end = analysis_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": analysis_text}
            
            json_str = analysis_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": analysis_text}
        
        except Exception as e:
            return {"error": f"Error processing analysis: {e}", "raw_response": analysis_text}
    
    def generate_summary(self, 
                        correlated_findings: Dict[str, Any],
                        problem_description: str = None) -> Dict[str, Any]:
        """
        Generate a concise summary of the analysis results.
        
        Args:
            correlated_findings: Results from correlation analysis
            problem_description: User-provided description of the problem (optional)
            
        Returns:
            Dictionary with analysis summary
        """
        if not correlated_findings:
            return {"error": "No correlated findings available for summary"}
        
        # Construct the prompt
        system_message = {
            "role": "system",
            "content": """
            You are a Kubernetes expert creating an executive summary of a root cause analysis.
            Create a clear, actionable summary that non-experts can understand.
            Focus on:
            1. The main issues identified
            2. Root causes
            3. Impact on the system
            4. Clear recommendations prioritized by importance
            5. Next steps
            
            Your response should be in JSON format with the following structure:
            {
                "executive_summary": "Brief paragraph summarizing the situation and key findings",
                "key_issues": [
                    {
                        "title": "Issue title",
                        "description": "Brief description",
                        "impact": "Impact description",
                        "root_cause": "Root cause description"
                    }
                ],
                "recommendations": [
                    {
                        "action": "Recommended action",
                        "priority": "high|medium|low",
                        "expected_outcome": "What this will solve",
                        "implementation_complexity": "high|medium|low"
                    }
                ],
                "next_steps": ["step1", "step2", "step3"]
            }
            """
        }
        
        user_message_content = "Here are the correlated findings for summarization:\n\n"
        
        if problem_description:
            user_message_content += f"Problem Description: {problem_description}\n\n"
        
        user_message_content += f"Correlated Findings:\n{json.dumps(correlated_findings, indent=2)}\n\n"
        
        user_message_content += "Please create an executive summary with clear recommendations."
        
        user_message = {
            "role": "user",
            "content": user_message_content
        }
        
        # Generate the summary
        summary_text = self.generate_completion(
            [system_message, user_message],
            temperature=0.2,
            max_tokens=2000
        )
        
        # Extract the JSON part
        try:
            # Find JSON object in the response
            json_start = summary_text.find("{")
            json_end = summary_text.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                return {"error": "Could not extract JSON from LLM response", "raw_response": summary_text}
            
            json_str = summary_text[json_start:json_end]
            result = json.loads(json_str)
            
            return result
        
        except json.JSONDecodeError:
            return {"error": "Invalid JSON in LLM response", "raw_response": summary_text}
        
        except Exception as e:
            return {"error": f"Error processing summary: {e}", "raw_response": summary_text}