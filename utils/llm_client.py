import os
import sys
import json
from typing import Dict, List, Any, Optional, Union
import openai
from openai import OpenAI
import anthropic
from anthropic import Anthropic

class LLMClient:
    """
    Client for interacting with LLM providers (OpenAI and Anthropic).
    Implements the Model Context Protocol (MCP) for K8s root cause analysis.
    """
    
    def __init__(self, provider: str = "openai"):
        """
        Initialize the LLM client.
        
        Args:
            provider: LLM provider to use ("openai" or "anthropic")
        """
        self.provider = provider.lower()
        
        if self.provider == "openai":
            openai_key: str = (os.environ.get('OPENAI_API_KEY') or
                           sys.exit('OPENAI_API_KEY environment variable must be set'))
            self.client = OpenAI(api_key=openai_key)
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024
            # do not change this unless explicitly requested by the user
            self.model = "gpt-4o"
            
        elif self.provider == "anthropic":
            anthropic_key: str = (os.environ.get('ANTHROPIC_API_KEY') or
                           sys.exit('ANTHROPIC_API_KEY environment variable must be set'))
            self.client = Anthropic(api_key=anthropic_key)
            #the newest Anthropic model is "claude-3-5-sonnet-20241022" which was released October 22, 2024
            self.model = "claude-3-5-sonnet-20241022"
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'openai' or 'anthropic'.")
    
    def analyze(self, 
              context: Dict[str, Any],
              tools: List[Dict[str, Any]],
              system_prompt: str,
              temperature: float = 0.1) -> Dict[str, Any]:
        """
        Run analysis following the Model Context Protocol (MCP).
        
        Args:
            context: Context information for the analysis task
            tools: List of available tools for the agent to use
            system_prompt: System prompt to define agent's role and approach
            temperature: Sampling temperature (lower = more deterministic)
            
        Returns:
            Dict containing the analysis results and reasoning
        """
        # Format the context into a prompt
        prompt = self._format_context(context)
        
        # Run the MCP reasoning loop
        result = self._mcp_reasoning_loop(
            prompt=prompt,
            system_prompt=system_prompt,
            tools=tools,
            temperature=temperature
        )
        
        return result
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """
        Format context into a structured prompt for the LLM.
        
        Args:
            context: Dictionary containing analysis context
            
        Returns:
            Formatted prompt string for the LLM
        """
        prompt_parts = ["# Kubernetes Root Cause Analysis Task\n\n"]
        
        # Add context components
        if "namespace" in context:
            prompt_parts.append(f"## Namespace: {context['namespace']}\n\n")
        
        if "context" in context:
            prompt_parts.append(f"## Kubernetes Context: {context['context']}\n\n")
        
        if "problem_description" in context:
            prompt_parts.append(f"## Problem Description:\n{context['problem_description']}\n\n")
        
        # Add data sections
        if "metrics" in context:
            prompt_parts.append("## Metrics Data:\n```json\n")
            prompt_parts.append(json.dumps(context["metrics"], indent=2))
            prompt_parts.append("\n```\n\n")
        
        if "logs" in context:
            prompt_parts.append("## Logs Data:\n")
            if isinstance(context["logs"], dict):
                for pod, logs in context["logs"].items():
                    prompt_parts.append(f"### Pod: {pod}\n```\n")
                    # Truncate if logs are too long
                    if len(logs) > 2000:
                        prompt_parts.append(logs[:2000] + "...(truncated)")
                    else:
                        prompt_parts.append(logs)
                    prompt_parts.append("\n```\n\n")
            else:
                prompt_parts.append("```\n")
                prompt_parts.append(str(context["logs"]))
                prompt_parts.append("\n```\n\n")
        
        if "events" in context:
            prompt_parts.append("## Events Data:\n```json\n")
            prompt_parts.append(json.dumps(context["events"], indent=2))
            prompt_parts.append("\n```\n\n")
        
        if "topology" in context:
            prompt_parts.append("## Topology Data:\n```json\n")
            prompt_parts.append(json.dumps(context["topology"], indent=2))
            prompt_parts.append("\n```\n\n")
        
        if "traces" in context:
            prompt_parts.append("## Traces Data:\n```json\n")
            prompt_parts.append(json.dumps(context["traces"], indent=2))
            prompt_parts.append("\n```\n\n")
        
        # Task instructions
        prompt_parts.append("## Your Task:\n")
        prompt_parts.append("1. Analyze the provided information to identify potential root causes of the problem\n")
        prompt_parts.append("2. Use available tools to gather additional information as needed\n")
        prompt_parts.append("3. Formulate a comprehensive diagnosis with supporting evidence\n")
        prompt_parts.append("4. Recommend clear remediation steps\n")
        
        return "".join(prompt_parts)
    
    def _mcp_reasoning_loop(self, 
                          prompt: str, 
                          system_prompt: str,
                          tools: List[Dict[str, Any]],
                          temperature: float = 0.1,
                          max_iterations: int = 5) -> Dict[str, Any]:
        """
        Execute a reasoning loop following the Model Context Protocol.
        Implements a tool-using reasoning process where the model can:
        1. Observe (context & tool output)
        2. Think (analyze observations)
        3. Act (use tools to gather more information)
        
        Args:
            prompt: Initial context and task prompt
            system_prompt: Instructions for the agent's role and reasoning approach
            tools: List of tool specifications
            temperature: Sampling temperature
            max_iterations: Maximum iterations for the reasoning loop
            
        Returns:
            Dict containing the final analysis, reasoning process, and tool usage
        """
        if self.provider == "openai":
            return self._mcp_reasoning_loop_openai(prompt, system_prompt, tools, temperature, max_iterations)
        else:
            return self._mcp_reasoning_loop_anthropic(prompt, system_prompt, tools, temperature, max_iterations)
    
    def _mcp_reasoning_loop_openai(self, 
                                prompt: str, 
                                system_prompt: str,
                                tools: List[Dict[str, Any]],
                                temperature: float = 0.1,
                                max_iterations: int = 5) -> Dict[str, Any]:
        """
        Execute MCP reasoning loop with OpenAI
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        reasoning_steps = []
        tool_calls_history = []
        
        for i in range(max_iterations):
            # Get response from model
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                tools=tools
            )
            
            assistant_message = {"role": "assistant"}
            
            if response.choices[0].message.content:
                assistant_message["content"] = response.choices[0].message.content
                reasoning_steps.append({
                    "step": i + 1,
                    "type": "thinking",
                    "content": response.choices[0].message.content
                })
            
            # Process tool calls if present
            if response.choices[0].message.tool_calls:
                assistant_message["tool_calls"] = response.choices[0].message.tool_calls
                
                for tool_call in response.choices[0].message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    reasoning_steps.append({
                        "step": i + 1,
                        "type": "tool_call",
                        "tool": function_name,
                        "arguments": function_args
                    })
                    
                    # Execute the tool
                    try:
                        function_response = self.execute_tool(function_name, function_args)
                        
                        tool_calls_history.append({
                            "tool": function_name,
                            "arguments": function_args,
                            "result": function_response,
                            "success": True
                        })
                        
                        # Add tool response to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(function_response)
                        })
                        
                        reasoning_steps.append({
                            "step": i + 1,
                            "type": "observation",
                            "tool": function_name,
                            "result": function_response
                        })
                        
                    except Exception as e:
                        error_message = f"Error executing {function_name}: {str(e)}"
                        
                        tool_calls_history.append({
                            "tool": function_name,
                            "arguments": function_args,
                            "error": error_message,
                            "success": False
                        })
                        
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps({"error": error_message})
                        })
                        
                        reasoning_steps.append({
                            "step": i + 1,
                            "type": "error",
                            "tool": function_name,
                            "error": error_message
                        })
                
            # Add assistant message to conversation
            messages.append(assistant_message)
            
            # Check if we have tool calls - if not, we can conclude
            if not response.choices[0].message.tool_calls:
                break
        
        # Final conclusion without tool options
        final_response = self.client.chat.completions.create(
            model=self.model,
            messages=messages + [
                {"role": "user", "content": "Based on your analysis, please provide a final comprehensive root cause analysis with clear evidence and remediation steps."}
            ],
            temperature=temperature,
        )
        
        final_analysis = final_response.choices[0].message.content
        
        return {
            "reasoning_steps": reasoning_steps,
            "tool_calls": tool_calls_history,
            "final_analysis": final_analysis,
            "conversation": messages
        }
    
    def _mcp_reasoning_loop_anthropic(self, 
                                    prompt: str, 
                                    system_prompt: str,
                                    tools: List[Dict[str, Any]],
                                    temperature: float = 0.1,
                                    max_iterations: int = 5) -> Dict[str, Any]:
        """
        Execute MCP reasoning loop with Anthropic
        """
        anthropic_messages = [
            {"role": "user", "content": prompt}
        ]
        
        reasoning_steps = []
        tool_calls_history = []
        
        for i in range(max_iterations):
            # Get response from model
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=temperature,
                system=system_prompt,
                messages=anthropic_messages,
                tools=tools
            )
            
            # Handle text content
            if message.content:
                reasoning_steps.append({
                    "step": i + 1,
                    "type": "thinking",
                    "content": message.content[0].text
                })
                
                anthropic_messages.append({
                    "role": "assistant", 
                    "content": message.content[0].text
                })
            
            # Handle tool calls
            if hasattr(message, 'tool_use') and message.tool_use:
                tool_uses = []
                
                for tool_use in message.tool_use:
                    function_name = tool_use.name
                    function_args = tool_use.input
                    
                    reasoning_steps.append({
                        "step": i + 1,
                        "type": "tool_call",
                        "tool": function_name,
                        "arguments": function_args
                    })
                    
                    # Execute the tool
                    try:
                        function_response = self.execute_tool(function_name, function_args)
                        
                        tool_calls_history.append({
                            "tool": function_name,
                            "arguments": function_args,
                            "result": function_response,
                            "success": True
                        })
                        
                        tool_uses.append({
                            "type": "tool_use",
                            "id": tool_use.id,
                            "name": function_name,
                            "input": function_args
                        })
                        
                        # Add tool response for next iteration
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_use.id,
                                    "content": json.dumps(function_response)
                                }
                            ]
                        })
                        
                        reasoning_steps.append({
                            "step": i + 1,
                            "type": "observation",
                            "tool": function_name,
                            "result": function_response
                        })
                        
                    except Exception as e:
                        error_message = f"Error executing {function_name}: {str(e)}"
                        
                        tool_calls_history.append({
                            "tool": function_name,
                            "arguments": function_args,
                            "error": error_message,
                            "success": False
                        })
                        
                        # Add error for next iteration
                        anthropic_messages.append({
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_use.id,
                                    "content": json.dumps({"error": error_message})
                                }
                            ]
                        })
                        
                        reasoning_steps.append({
                            "step": i + 1,
                            "type": "error",
                            "tool": function_name,
                            "error": error_message
                        })
                
                # If no tool calls, we can conclude
                if not tool_uses:
                    break
            else:
                # No tool calls, we can conclude
                break
        
        # Final conclusion without tool options
        anthropic_messages.append({
            "role": "user", 
            "content": "Based on your analysis, please provide a final comprehensive root cause analysis with clear evidence and remediation steps."
        })
        
        final_message = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=anthropic_messages,
        )
        
        final_analysis = final_message.content[0].text
        
        return {
            "reasoning_steps": reasoning_steps,
            "tool_calls": tool_calls_history,
            "final_analysis": final_analysis,
            "anthropic_messages": anthropic_messages
        }
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute a tool based on its name and arguments.
        This method should be implemented by the agent using this client.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
        """
        raise NotImplementedError("Tool execution must be implemented by the agent")