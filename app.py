import streamlit as st
from utils.helper import setup_page

# Setup the page configuration must be the first Streamlit command
setup_page()

import os
import yaml
import time
from components.sidebar import render_sidebar
from components.visualization import render_visualization
from components.report import render_report
from components.interactive_session import (
    init_interactive_session, 
    render_interactive_session
)
from components.chatbot_interface import (
    init_chatbot_interface,
    render_chatbot_interface
)
from agents.mcp_coordinator import MCPCoordinator
from utils.k8s_client import K8sClient
from utils.db_handler import DBHandler
# Don't use mock implementations - user requires live K8s cluster
# from utils.mock_k8s_client import MockK8sClient

# Initialize the Kubernetes client using your live cluster configuration
k8s_client = K8sClient()

# Initialize database handler
db_handler = DBHandler()

# Check connection status
if not k8s_client.is_connected():
    st.sidebar.error("❌ Could not connect to your Kubernetes cluster")
    error_message = k8s_client.get_connection_error() or "Unknown connection error"
    server_url = k8s_client.server_url
    
    # If the error has the ngrok error code, display a more specific message
    if "ERR_NGROK_3200" in error_message:
        st.sidebar.error("The ngrok tunnel endpoint is offline")
        st.sidebar.info(f"The ngrok endpoint {server_url} in your kubeconfig is not active. Please restart your ngrok tunnel or update the kubeconfig with a new endpoint.")

# Initialize environment - try Anthropic by default since OpenAI quota is exceeded
llm_provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
if llm_provider not in ["openai", "anthropic"]:
    st.warning(f"Unknown LLM provider: {llm_provider}. Defaulting to Anthropic.")
    llm_provider = "anthropic"

# Check if OpenAI API key has a quota issue - if it's the selected provider
if llm_provider == "openai":
    try:
        from utils.llm_client_improved import LLMClient
        test_client = LLMClient("openai")
        # Test with a minimal prompt
        test_response = test_client.generate_completion("This is a test to check API quota.")
        if isinstance(test_response, str) and test_response.startswith('{"error":'):
            import json
            error_data = json.loads(test_response)
            if "API Quota Exceeded" in error_data.get("error", ""):
                st.warning("⚠️ OpenAI API key has exceeded its quota. Switching to Anthropic.")
                llm_provider = "anthropic"
                os.environ["LLM_PROVIDER"] = "anthropic"
    except Exception as e:
        st.warning(f"⚠️ Error checking OpenAI API status: {str(e)}. Using Anthropic instead.")
        llm_provider = "anthropic"
        os.environ["LLM_PROVIDER"] = "anthropic"

# Initialize the MCP coordinator
coordinator = MCPCoordinator(k8s_client, provider=llm_provider)

# Initialize session state for UI mode
if 'ui_mode' not in st.session_state:
    st.session_state.ui_mode = 'chatbot'  # Default to chatbot UI

# Store globally available data in session state
if 'selected_context' not in st.session_state:
    st.session_state.selected_context = None
if 'selected_namespace' not in st.session_state:
    st.session_state.selected_namespace = None
if 'db_handler' not in st.session_state:
    st.session_state.db_handler = db_handler

# Main application
def main():
    # Display LLM provider info
    with st.sidebar.expander("LLM Configuration"):
        st.write(f"Using {llm_provider.upper()} as the LLM provider")
        if st.button("Switch Provider"):
            new_provider = "anthropic" if llm_provider == "openai" else "openai"
            os.environ["LLM_PROVIDER"] = new_provider
            st.rerun()
    
    # Render the sidebar
    selected_context, selected_namespace, analysis_type, submitted, problem_description, selected_investigation = render_sidebar(k8s_client)
    
    # Store the selected context and namespace in session state
    st.session_state.selected_context = selected_context
    st.session_state.selected_namespace = selected_namespace
    
    # Check if we're not connected to a Kubernetes cluster
    if not k8s_client.is_connected():
        st.warning("Not connected to any Kubernetes cluster. Please configure your kubeconfig or connect to a cluster.")
        st.info("This application requires a Kubernetes cluster connection. You have a few options:")
        
        # Minikube option
        with st.expander("Option 1: Use Minikube"):
            st.markdown("""
            1. Install Minikube: Follow the [official instructions](https://minikube.sigs.k8s.io/docs/start/)
            2. Start Minikube: `minikube start`
            3. Set up kubeconfig: `export KUBECONFIG=~/.kube/config`
            """)
        
        # Kind option
        with st.expander("Option 2: Use Kind (Kubernetes IN Docker)"):
            st.markdown("""
            1. Install Kind: Follow the [official instructions](https://kind.sigs.k8s.io/docs/user/quick-start/)
            2. Create a cluster: `kind create cluster`
            3. Set up kubeconfig: `export KUBECONFIG=~/.kube/config`
            """)
        
        # Remote cluster option
        with st.expander("Option 3: Connect to a remote cluster"):
            st.markdown("""
            1. Obtain the kubeconfig file from your cluster administrator
            2. Set up kubeconfig: `export KUBECONFIG=/path/to/your/kubeconfig`
            """)
        
        return
    
    # Check if we have a current investigation in session state
    current_investigation_id = st.session_state.get('current_investigation_id')
    view_mode = st.session_state.get('view_mode', 'welcome')
    
    # Debugging information
    with st.sidebar.expander("Debug Information", expanded=False):
        st.write("Current Investigation ID:", current_investigation_id)
        st.write("Selected Investigation:", selected_investigation)
        st.write("View Mode:", view_mode)
        st.write("Submitted:", submitted)
        st.write("Session State Keys:", list(st.session_state.keys()))
    
    # If we're in chat view mode with a newly created investigation
    if view_mode == 'chat' and current_investigation_id:
        st.success(f"Working with investigation: {current_investigation_id}")
        print(f"DEBUG: Rendering chatbot interface for investigation {current_investigation_id} (from view_mode)")
        render_chatbot_interface(
            coordinator=coordinator, 
            k8s_client=k8s_client,
            investigation_id=current_investigation_id,
            db_handler=db_handler
        )
    
    # If we have a selected investigation from sidebar, render that
    elif selected_investigation:
        st.info(f"Viewing investigation: {selected_investigation}")
        print(f"DEBUG: Rendering chatbot interface for investigation {selected_investigation} (from sidebar)")
        render_chatbot_interface(
            coordinator=coordinator, 
            k8s_client=k8s_client,
            investigation_id=selected_investigation,
            db_handler=db_handler
        )
    
    # If we have a current investigation in session state, render that
    elif current_investigation_id:
        st.success(f"Working with current investigation: {current_investigation_id}")
        print(f"DEBUG: Rendering chatbot interface for investigation {current_investigation_id} (from session state)")
        render_chatbot_interface(
            coordinator=coordinator, 
            k8s_client=k8s_client,
            investigation_id=current_investigation_id,
            db_handler=db_handler
        )
    
    # If we've submitted a new investigation, create it and render the chatbot
    elif submitted:
        st.info("New investigation submitted - checking process")
        # This is a fallback - the investigation should be created in the sidebar component
        # and should set current_investigation_id in session state
        investigation_id = st.session_state.get('current_investigation_id')
        if investigation_id:
            st.success(f"Investigation started! ID: {investigation_id}")
            print(f"DEBUG: Rendering chatbot interface for investigation {investigation_id} (from submitted)")
            render_chatbot_interface(
                coordinator=coordinator, 
                k8s_client=k8s_client,
                investigation_id=investigation_id,
                db_handler=db_handler
            )
        else:
            st.error("Failed to create investigation. Please try again. (No ID found)")
            st.write("Please click New Investigation again and provide a title.")
    # Otherwise, show a welcome message
    else:
        st.title("Kubernetes Root Cause Analysis System")
        st.write("A multi-agent system for analyzing and troubleshooting cloud-native applications")
        
        st.info("👈 Start by selecting an existing investigation from the sidebar or create a new one.")
        
        # Show a brief overview of how to use the system
        with st.expander("How to use this system"):
            st.markdown("""
            ## How to use the Kubernetes Root Cause Analysis System
            
            This AI-powered system helps you diagnose and fix issues in your Kubernetes cluster:
            
            1. **Create a new investigation** by clicking the "New Investigation" button in the sidebar
            2. **Select your Kubernetes context and namespace** to analyze
            3. **Provide a title and description** of the problem you're experiencing
            4. **Start the investigation** and interact with the AI chatbot
            5. **Click on suggested actions** to guide the investigation
            6. **View past investigations** in the sidebar to continue previous work
            
            The system will analyze your Kubernetes resources, logs, events, and metrics to identify root causes.
            """)
        
        # Show system capabilities
        with st.expander("System Capabilities"):
            st.markdown("""
            ## System Capabilities
            
            This system can analyze:
            
            - **Kubernetes resources**: Pods, Deployments, Services, etc.
            - **Container logs**: Identify errors and exceptions
            - **Kubernetes events**: Detect scheduling issues, crashes, etc.
            - **Resource metrics**: CPU, memory usage, etc.
            - **Service topology**: Dependencies and networking issues
            - **Distributed traces**: Request flows and latency issues
            
            The AI agents collaborate to analyze different aspects of your cluster and provide intelligent recommendations.
            """)
        
        # Show the UI toggle
        st.markdown("---")
        st.caption("This is a new redesigned UI. If you prefer the classic UI, you can switch back:")
        if st.button("Switch to Classic UI"):
            st.session_state.ui_mode = 'classic'
            st.rerun()

if __name__ == "__main__":
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    
    # Initialize interactive session state
    init_interactive_session()
    
    # Initialize chatbot interface
    init_chatbot_interface()
        
    main()