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
from agents.mcp_coordinator import MCPCoordinator
from utils.k8s_client import K8sClient
from utils.mock_k8s_client import MockK8sClient

# Try to initialize the real Kubernetes client
real_k8s_client = K8sClient()

# If it's not connected, use the mock client instead
if not real_k8s_client.is_connected():
    st.sidebar.warning("⚠️ Using mock Kubernetes data for testing")
    k8s_client = MockK8sClient()
else:
    k8s_client = real_k8s_client

# Initialize environment
llm_provider = os.environ.get("LLM_PROVIDER", "openai").lower()
if llm_provider not in ["openai", "anthropic"]:
    st.warning(f"Unknown LLM provider: {llm_provider}. Defaulting to OpenAI.")
    llm_provider = "openai"

# Initialize the MCP coordinator
coordinator = MCPCoordinator(k8s_client, provider=llm_provider)

# Main application
def main():
    st.title("Kubernetes Root Cause Analysis System")
    st.write("A multi-agent system for analyzing and troubleshooting cloud-native applications")
    
    # Display LLM provider info
    with st.sidebar.expander("LLM Configuration"):
        st.write(f"Using {llm_provider.upper()} as the LLM provider")
        if st.button("Switch Provider"):
            new_provider = "anthropic" if llm_provider == "openai" else "openai"
            os.environ["LLM_PROVIDER"] = new_provider
            st.experimental_rerun()
    
    # Render the sidebar
    selected_context, selected_namespace, analysis_type, submitted, problem_description = render_sidebar(k8s_client)
    
    # Main content area
    if isinstance(k8s_client, MockK8sClient):
        st.info("⚠️ Using mock Kubernetes data for testing and demonstration purposes.")
        st.write("The analysis will be performed on a simulated Kubernetes cluster with deliberately problematic microservices.")
        with st.expander("Mock Cluster Description"):
            st.markdown("""
            ## Mock Cluster Description
            
            This mock cluster includes the following microservices in the `test-microservices` namespace:
            
            1. **Frontend (nginx)** - Functioning normally
            2. **Backend** - High CPU usage issue (90% utilization)
            3. **Database** - Frequent restart issue (CrashLoopBackOff)
            4. **API Gateway** - Missing environment variable issue (Failed state)
            5. **Resource Service** - High memory usage issue (89.84% utilization)
            
            Additionally, a network policy is incorrectly blocking traffic to the backend service.
            
            These issues are deliberately injected to demonstrate the root cause analysis capabilities of the system.
            """)
    elif not k8s_client.is_connected():
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

    if submitted:
        with st.spinner(f"Running {analysis_type} analysis on namespace {selected_namespace}..."):
            # Run analysis based on the selected type and context
            analysis_results = coordinator.run_analysis(
                analysis_type=analysis_type,
                namespace=selected_namespace,
                context=selected_context,
                problem_description=problem_description
            )
            
            if 'error' in analysis_results:
                st.error(f"Error during analysis: {analysis_results['error']}")
                return
                
            # Store results in session state
            st.session_state.analysis_results = analysis_results
            st.session_state.analysis_complete = True
    
    # Display results if analysis is complete
    if st.session_state.get('analysis_complete', False):
        analysis_results = st.session_state.analysis_results
        
        # Display visualization
        render_visualization(analysis_results, analysis_type)
        
        # Display detailed report
        render_report(analysis_results, analysis_type)

        # Export functionality
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Export Analysis Report"):
                report_yaml = yaml.dump(analysis_results, default_flow_style=False)
                st.download_button(
                    label="Download YAML Report",
                    data=report_yaml,
                    file_name=f"k8s_analysis_{analysis_type}_{time.strftime('%Y%m%d_%H%M%S')}.yaml",
                    mime="application/x-yaml"
                )
        
        with col2:
            if st.button("Clear Results"):
                st.session_state.analysis_complete = False
                st.session_state.analysis_results = None
                st.experimental_rerun()

if __name__ == "__main__":
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
        
    main()
