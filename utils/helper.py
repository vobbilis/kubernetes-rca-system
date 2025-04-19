import streamlit as st
import subprocess
import re
import json
import yaml
from datetime import datetime

def setup_page():
    """
    Set up the page configuration for the Streamlit app.
    """
    try:
        st.set_page_config(
            page_title="Kubernetes Root Cause Analysis",
            page_icon="🔍",
            layout="wide",
            menu_items={
                'Get Help': 'https://kubernetes.io/docs/tasks/debug/debug-application/',
                'Report a bug': 'https://github.com/kubernetes/kubernetes/issues',
                'About': 'AI-Powered Kubernetes Root Cause Analysis Tool'
            },
            initial_sidebar_state="expanded"
        )
    except Exception as e:
        # Already set up, ignore the exception
        pass

def run_kubectl_command(command_args):
    """
    Run a kubectl command and return the result.
    
    Args:
        command_args: List of command arguments (excluding 'kubectl')
        
    Returns:
        dict: Command result with keys 'success', 'output', and 'error'
    """
    cmd = ["kubectl"] + command_args
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {
            'success': True,
            'output': result.stdout,
            'error': None
        }
    except subprocess.CalledProcessError as e:
        return {
            'success': False,
            'output': None,
            'error': e.stderr
        }

def parse_kubectl_output(output, output_format='json'):
    """
    Parse kubectl command output into Python objects.
    
    Args:
        output: String output from kubectl command
        output_format: Format of the output ('json' or 'yaml')
        
    Returns:
        object: Parsed output as Python object
    """
    if not output:
        return None
    
    try:
        if output_format == 'json':
            return json.loads(output)
        elif output_format == 'yaml':
            return yaml.safe_load(output)
        else:
            return output
    except Exception as e:
        print(f"Error parsing kubectl output: {e}")
        return None

def format_datetime(dt_str):
    """
    Format a datetime string into a human-readable format.
    
    Args:
        dt_str: Datetime string in ISO format
        
    Returns:
        str: Formatted datetime string
    """
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return dt_str

def parse_resource_quantity(quantity_str):
    """
    Parse Kubernetes resource quantity string to a number.
    
    Args:
        quantity_str: Resource quantity string (e.g., '100Mi', '0.5')
        
    Returns:
        float: Resource quantity in appropriate units
    """
    try:
        if not quantity_str:
            return 0.0
        
        # Define unit multipliers
        units = {
            'n': 1e-9,
            'u': 1e-6,
            'm': 1e-3,
            'K': 1e3, 'k': 1e3,
            'M': 1e6,
            'G': 1e9,
            'T': 1e12,
            'P': 1e15,
            'E': 1e18,
            'Ki': 2**10,
            'Mi': 2**20,
            'Gi': 2**30,
            'Ti': 2**40,
            'Pi': 2**50,
            'Ei': 2**60
        }
        
        # Match numeric part and unit
        match = re.match(r'^(\d*\.?\d*)([A-Za-z]*)$', quantity_str)
        if match:
            value, unit = match.groups()
            value = float(value) if value else 0.0
            
            if unit in units:
                return value * units[unit]
            else:
                return value
        else:
            return float(quantity_str)
    except (ValueError, TypeError):
        return 0.0

def truncate_long_string(string, max_length=100):
    """
    Truncate a long string with an ellipsis.
    
    Args:
        string: String to truncate
        max_length: Maximum length before truncation
        
    Returns:
        str: Truncated string
    """
    if not string:
        return ""
    
    if len(string) <= max_length:
        return string
    
    return string[:max_length] + "..."

def format_duration(seconds):
    """
    Format a duration in seconds to a human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h"
    else:
        days = seconds / 86400
        return f"{days:.1f}d"
