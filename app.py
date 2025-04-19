import streamlit as st
import os
import yaml
import time
from components.sidebar import render_sidebar
from components.visualization import render_visualization
from components.report import render_report
from agents.mcp_coordinator import MCPCoordinator
from utils.k8s_client import K8sClient
from utils.helper import setup_page

# Initialize the Kubernetes client
k8s_client = K8sClient()

# Initialize environment
llm_provider = os.environ.get("LLM_PROVIDER", "openai").lower()
if llm_provider not in ["openai", "anthropic"]:
    st.warning(f"Unknown LLM provider: {llm_provider}. Defaulting to OpenAI.")
    llm_provider = "openai"

# Initialize the MCP coordinator
coordinator = MCPCoordinator(k8s_client, provider=llm_provider)

# Setup the page configuration
setup_page()

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
