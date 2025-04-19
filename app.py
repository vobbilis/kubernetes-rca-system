import streamlit as st
import os
import yaml
import time
from components.sidebar import render_sidebar
from components.visualization import render_visualization
from components.report import render_report
from agents.coordinator import Coordinator
from utils.k8s_client import K8sClient
from utils.helper import setup_page

# Initialize the Kubernetes client
k8s_client = K8sClient()

# Initialize the coordinator agent
coordinator = Coordinator(k8s_client)

# Setup the page configuration
setup_page()

# Main application
def main():
    st.title("Kubernetes Root Cause Analysis System")
    st.write("A multi-agent system for analyzing and troubleshooting cloud-native applications")
    
    # Render the sidebar
    selected_context, selected_namespace, analysis_type, submitted = render_sidebar(k8s_client)
    
    # Main content area
    if not k8s_client.is_connected():
        st.warning("Not connected to any Kubernetes cluster. Please configure your kubeconfig or connect to a cluster.")
        st.info("You can set up kubectl on your machine and this tool will automatically use your configuration.")
        return

    if submitted:
        with st.spinner(f"Running {analysis_type} analysis on namespace {selected_namespace}..."):
            # Run analysis based on the selected type and context
            analysis_results = coordinator.run_analysis(
                analysis_type=analysis_type,
                namespace=selected_namespace,
                context=selected_context
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
        if st.button("Export Analysis Report"):
            report_yaml = yaml.dump(analysis_results, default_flow_style=False)
            st.download_button(
                label="Download YAML Report",
                data=report_yaml,
                file_name=f"k8s_analysis_{analysis_type}_{time.strftime('%Y%m%d_%H%M%S')}.yaml",
                mime="application/x-yaml"
            )

if __name__ == "__main__":
    # Initialize session state
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
        
    main()
