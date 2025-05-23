import os
import json
import sys
import logging
import time
from typing import Dict, List, Any, Optional, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage
from anthropic import Anthropic
from anthropic.types import Message

# Import the prompt logger
from utils.prompt_logger import get_logger

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
            self.default_claude_model = "claude-3-5-sonnet-20241022"
        
        else:
            logger.error(f"Unknown provider: {provider}")
            sys.exit(f"Unknown provider: {provider}. Only 'openai' and 'anthropic' are supported.")
    
    def analyze(self, context: Dict[str, Any], tools: List[Dict] = None, system_prompt: str = None) -> Dict[str, Any]:
        """
        Analyze data in the provided context using the LLM.
        
        Args:
            context: Dictionary with data to analyze (including problem_description)
            tools: List of tools/functions the LLM can use (optional)
            system_prompt: System prompt to set context for the LLM (optional)
            
        Returns:
            Dictionary with analysis results including final_analysis and reasoning_steps
        """
        problem_description = context.get("problem_description", "")
        if not problem_description:
            logger.warning("No problem description provided for analysis")
            return {"error": "No problem description provided"}
        
        # Create messages list
        messages = []
        
        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # Add the problem description
        messages.append({"role": "user", "content": problem_description})
        
        try:
            # Generate completion
            response_text = self.generate_completion(messages)
            
            # Check if the response is a JSON error message
            if response_text.startswith('{"error":'):
                error_data = json.loads(response_text)
                return {
                    "error": error_data.get("error", "Unknown error"),
                    "final_analysis": error_data.get("message", "Error occurred"),
                    "reasoning_steps": []
                }
            
            # Return analysis results
            return {
                "final_analysis": response_text,
                "reasoning_steps": [
                    {
                        "observation": "Analyzed provided data",
                        "conclusion": "Generated analysis based on context"
                    }
                ]
            }
        except Exception as e:
            logger.error(f"Error in analyze: {e}")
            return {
                "error": f"Analysis failed: {str(e)}",
                "final_analysis": "Unable to complete analysis due to an error",
                "reasoning_steps": []
            }
        
    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a tool or function using the LLM.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            context: Additional context for the execution (optional)
            
        Returns:
            Dictionary with the tool execution results
        """
        # For now, just log the tool execution request and return a simple response
        logger.info(f"Tool execution request: {tool_name} with args {tool_args}")
        
        # Handle different tools
        if tool_name == "get_logs":
            return {
                "result": f"Retrieved logs for {tool_args.get('pod_name', 'unknown pod')}",
                "execution_status": "success"
            }
        elif tool_name == "get_metrics":
            return {
                "result": f"Retrieved metrics for {tool_args.get('resource_name', 'unknown resource')}",
                "execution_status": "success"
            }
        elif tool_name == "check_status":
            return {
                "result": f"Checked status of {tool_args.get('resource_name', 'unknown resource')}",
                "execution_status": "success"
            }
        else:
            return {
                "result": f"Unknown tool: {tool_name}",
                "execution_status": "error"
            }
    
    def generate_structured_output(self, prompt: Union[str, List[Dict]], 
                                 model: Optional[str] = None,
                                 temperature: float = 0.2,
                                 user_query: Optional[str] = None,
                                 system_prompt: Optional[str] = None,
                                 investigation_id: Optional[str] = None,
                                 accumulated_findings: Optional[List[str]] = None,
                                 namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate structured output in JSON format from the LLM.
        
        Args:
            prompt: Prompt text or list of message dicts
            model: Model to use (optional, defaults to the provider's default model)
            temperature: Sampling temperature (0.0 to 1.0)
            user_query: Original user query for logging
            system_prompt: Optional system prompt to set context for the LLM
            investigation_id: Optional ID of the current investigation for logging
            accumulated_findings: List of findings from previous interactions
            namespace: Kubernetes namespace for context
            
        Returns:
            dict: Parsed JSON response
        """
        if self.provider == "openai":
            try:
                # Handle different prompt types
                if isinstance(prompt, str):
                    messages = [{"role": "user", "content": prompt}]
                else:
                    messages = prompt
                
                # Get formatted prompt for logging
                formatted_prompt = ""
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted_prompt += f"{role.upper()}: {content}\n\n"
                
                # Make the API call
                response = self.openai_client.chat.completions.create(
                    model=model or self.default_model,
                    messages=messages,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    max_tokens=2000
                )
                
                content = response.choices[0].message.content
                
                # Get the prompt logger
                prompt_logger = get_logger()
                
                # Log the prompt and response
                if prompt_logger and user_query:
                    try:
                        parsed_json = json.loads(content)
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=parsed_json,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "openai",
                                "model": model or self.default_model,
                                "temperature": temperature,
                                "formatted": True
                            }
                        )
                    except json.JSONDecodeError:
                        # Still log even if JSON parsing fails
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=content,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "openai",
                                "model": model or self.default_model,
                                "temperature": temperature,
                                "parse_error": True
                            }
                        )
                
                # Parse the JSON response
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {content}")
                    # Try to extract JSON from the response if it contains markdown code blocks
                    if "```json" in content:
                        json_content = content.split("```json")[1].split("```")[0].strip()
                        try:
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON from markdown: {json_content}")
                    
                    # Return a simplified error response
                    return {"error": "Failed to parse structured output", "raw_response": content}
                    
            except Exception as e:
                logger.error(f"Error while generating structured output with OpenAI: {e}")
                return {"error": str(e)}
                
        elif self.provider == "anthropic":
            try:
                # Format the prompt for Claude
                system_content = None
                user_content = prompt
                
                # If a system_prompt was explicitly provided, use it
                if system_prompt is not None:
                    system_content = system_prompt
                
                # Otherwise try to extract from the messages
                elif isinstance(prompt, list):
                    # Extract system and user messages
                    system_messages = [m for m in prompt if m.get("role") == "system"]
                    user_messages = [m for m in prompt if m.get("role") == "user"]
                    
                    if system_messages:
                        system_content = system_messages[0].get("content")
                    
                    if user_messages:
                        user_content = user_messages[-1].get("content")
                    else:
                        user_content = "Analyze the given information and provide a JSON response."
                
                # Add JSON format instruction
                if isinstance(user_content, str):
                    user_content += "\n\nPlease provide your response in valid JSON format."
                
                # Format prompt for logging
                formatted_prompt = f"SYSTEM: {system_content or 'Not specified'}\n\nUSER: {user_content}"
                
                # Make API call - Always pass a string or None to system
                final_system = system_content if isinstance(system_content, str) else None
                
                messages_payload = [
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
                
                response = self.anthropic_client.messages.create(
                    model=model or self.default_claude_model,
                    max_tokens=2000,
                    temperature=temperature,
                    system=final_system,
                    messages=messages_payload
                )
                
                content = response.content[0].text
                
                # Get the prompt logger
                prompt_logger = get_logger()
                
                # Log the prompt and response
                if prompt_logger and user_query:
                    try:
                        parsed_json = json.loads(content)
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=parsed_json,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "anthropic",
                                "model": model or self.default_claude_model,
                                "temperature": temperature,
                                "formatted": True
                            }
                        )
                    except json.JSONDecodeError:
                        # Still log even if JSON parsing fails
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=content,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "anthropic",
                                "model": model or self.default_claude_model,
                                "temperature": temperature,
                                "parse_error": True
                            }
                        )
                
                # Parse the JSON response
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON response: {content}")
                    # Try to extract JSON from the response if it contains markdown code blocks
                    if "```json" in content:
                        json_content = content.split("```json")[1].split("```")[0].strip()
                        try:
                            return json.loads(json_content)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON from markdown: {json_content}")
                    
                    # Return a simplified error response
                    return {"error": "Failed to parse structured output", "raw_response": content}
                    
            except Exception as e:
                logger.error(f"Error while generating structured output with Anthropic: {e}")
                return {"error": str(e)}
                
        else:
            logger.error(f"Unsupported provider: {self.provider}")
            return {"error": f"Unsupported provider: {self.provider}"}
    
    def generate_completion(self, prompt: Union[str, List[Dict]], 
                           model: Optional[str] = None,
                           temperature: float = 0.2,
                           max_tokens: int = 2000,
                           system_prompt: Optional[str] = None,
                           investigation_id: Optional[str] = None,
                           user_query: Optional[str] = None,
                           accumulated_findings: Optional[List[str]] = None,
                           namespace: Optional[str] = None) -> str:
        """
        Generate a completion for the given prompt.
        
        Args:
            prompt: Prompt text or chat messages
            model: Model name to use (if None, use the default model)
            temperature: Sampling temperature
            max_tokens: Maximum number of tokens to generate
            system_prompt: Optional system prompt to set context for the LLM
            investigation_id: Optional ID of the current investigation for logging
            user_query: Original user query for logging
            accumulated_findings: List of findings from previous interactions
            namespace: Kubernetes namespace for context
            
        Returns:
            Generated completion text
        """
        if model is None:
            model = self.default_model
            
        # Get the prompt logger
        prompt_logger = get_logger()
        
        if self.provider == "openai":
            # Handle different prompt types
            if isinstance(prompt, str):
                messages = [{"role": "user", "content": prompt}]
            else:
                messages = prompt
            
            try:
                # Get formatted prompt for logging
                formatted_prompt = ""
                for msg in messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    formatted_prompt += f"{role.upper()}: {content}\n\n"
                
                # Make the API call
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                response_content = response.choices[0].message.content
                
                # Log the prompt and response
                if prompt_logger and user_query:
                    prompt_logger.log_interaction(
                        user_query=user_query or "Not provided",
                        prompt=formatted_prompt,
                        response=response_content,
                        investigation_id=investigation_id,
                        accumulated_findings=accumulated_findings,
                        namespace=namespace,
                        additional_context={
                            "provider": "openai",
                            "model": model,
                            "temperature": temperature,
                            "max_tokens": max_tokens
                        }
                    )
                
                return response_content
            
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")
                error_msg = str(e)
                
                # Check for quota exceeded error
                if "exceeded your current quota" in error_msg or "insufficient_quota" in error_msg:
                    quota_msg = """
                    API quota exceeded. This error occurs when:
                    1. The OpenAI API key has reached its usage limit
                    2. The billing information for the API key needs to be updated
                    
                    Please try one of the following:
                    - Switch to the Anthropic provider by changing the LLMClient initialization
                    - Provide a different OpenAI API key with available quota
                    - Update the billing information for your OpenAI account
                    """
                    logger.warning(quota_msg)
                    return json.dumps({
                        "error": "API Quota Exceeded",
                        "message": "The OpenAI API key has reached its usage limit. Please update billing details or use a different key.",
                        "recommendations": [
                            "Switch to Anthropic Claude API",
                            "Update billing information",
                            "Use a different OpenAI API key"
                        ]
                    })
                
                return json.dumps({
                    "error": "API Error",
                    "message": f"Error generating completion: {error_msg}",
                    "recommendations": [
                        "Try again with a different prompt",
                        "Check API key validity",
                        "Try a different model"
                    ]
                })
        
        elif self.provider == "anthropic":
            # Handle different prompt types
            if isinstance(prompt, str):
                system_content = "You are a Kubernetes expert analyzing cluster data for root cause analysis."
                user_content = prompt
                
                try:
                    # Format prompt for logging
                    formatted_prompt = f"SYSTEM: {system_content}\n\nUSER: {user_content}"
                    
                    # Make API call
                    # Ensure system_content is a string or None
                    system_prompt = system_content if isinstance(system_content, str) else None
                    
                    messages_payload = [{"role": "user", "content": user_content}]
                    
                    response = self.anthropic_client.messages.create(
                        model=model,
                        system=system_prompt,
                        messages=messages_payload,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    response_content = response.content[0].text
                    
                    # Log the prompt and response
                    if prompt_logger and user_query:
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=response_content,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "anthropic",
                                "model": model,
                                "temperature": temperature,
                                "max_tokens": max_tokens
                            }
                        )
                    
                    return response_content
                
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    error_msg = str(e)
                    
                    # Check for quota exceeded error
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or "billing" in error_msg.lower():
                        quota_msg = """
                        Anthropic API quota exceeded or rate limited. This error occurs when:
                        1. The Anthropic API key has reached its usage limit
                        2. The billing information for the API key needs to be updated
                        3. You are sending too many requests in a short time period
                        """
                        logger.warning(quota_msg)
                        return json.dumps({
                            "error": "API Quota Exceeded or Rate Limited",
                            "message": "The Anthropic API key has reached its usage limit or is being rate limited. Please wait or use a different key.",
                            "recommendations": [
                                "Switch to OpenAI API",
                                "Update billing information",
                                "Use a different Anthropic API key", 
                                "Wait a few minutes before trying again"
                            ]
                        })
                    
                    return json.dumps({
                        "error": "API Error",
                        "message": f"Error generating completion: {error_msg}",
                        "recommendations": [
                            "Try again with a different prompt",
                            "Check API key validity",
                            "Try a different model"
                        ]
                    })
            
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
                    # Format prompt for logging
                    formatted_prompt = f"SYSTEM: {system_content}\n\n"
                    for msg in messages:
                        role = msg.get("role", "unknown")
                        content = msg.get("content", "")
                        formatted_prompt += f"{role.upper()}: {content}\n\n"
                    
                    # Make API call
                    # Ensure system_content is a string or None
                    system_prompt = system_content if isinstance(system_content, str) else None
                    
                    response = self.anthropic_client.messages.create(
                        model=model,
                        system=system_prompt,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    response_content = response.content[0].text
                    
                    # Log the prompt and response
                    if prompt_logger and user_query:
                        prompt_logger.log_interaction(
                            user_query=user_query or "Not provided",
                            prompt=formatted_prompt,
                            response=response_content,
                            investigation_id=investigation_id,
                            accumulated_findings=accumulated_findings,
                            namespace=namespace,
                            additional_context={
                                "provider": "anthropic",
                                "model": model,
                                "temperature": temperature,
                                "max_tokens": max_tokens
                            }
                        )
                    
                    return response_content
                
                except Exception as e:
                    logger.error(f"Anthropic API error: {e}")
                    error_msg = str(e)
                    
                    # Check for quota exceeded error
                    if "quota" in error_msg.lower() or "rate limit" in error_msg.lower() or "billing" in error_msg.lower():
                        quota_msg = """
                        Anthropic API quota exceeded or rate limited. This error occurs when:
                        1. The Anthropic API key has reached its usage limit
                        2. The billing information for the API key needs to be updated
                        3. You are sending too many requests in a short time period
                        """
                        logger.warning(quota_msg)
                        return json.dumps({
                            "error": "API Quota Exceeded or Rate Limited",
                            "message": "The Anthropic API key has reached its usage limit or is being rate limited. Please wait or use a different key.",
                            "recommendations": [
                                "Switch to OpenAI API",
                                "Update billing information",
                                "Use a different Anthropic API key", 
                                "Wait a few minutes before trying again"
                            ]
                        })
                    
                    return json.dumps({
                        "error": "API Error",
                        "message": f"Error generating completion: {error_msg}",
                        "recommendations": [
                            "Try again with a different prompt",
                            "Check API key validity",
                            "Try a different model"
                        ]
                    })