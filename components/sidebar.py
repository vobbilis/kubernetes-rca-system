import streamlit as st

def render_sidebar(k8s_client):
    """
    Render the sidebar for the Kubernetes root cause analysis application.
    
    Args:
        k8s_client: Instance of the Kubernetes client
        
    Returns:
        tuple: (selected_context, selected_namespace, analysis_type, submitted, problem_description)
    """
    st.sidebar.title("Analysis Configuration")
    
    # Check if connected to Kubernetes
    if not k8s_client.is_connected():
        st.sidebar.warning("⚠️ Not connected to Kubernetes")
        st.sidebar.info("Please configure kubectl access to your cluster")
        return None, None, None, False, None
    
    # Kubernetes context selection
    available_contexts = k8s_client.get_available_contexts()
    current_context = k8s_client.get_current_context()
    
    selected_context = st.sidebar.selectbox(
        "Kubernetes Context",
        options=available_contexts,
        index=available_contexts.index(current_context) if current_context in available_contexts else 0,
        help="Select the Kubernetes context to analyze"
    )
    
    # Change context if needed
    if selected_context != current_context:
        with st.sidebar.spinner(f"Switching to context {selected_context}..."):
            if k8s_client.set_context(selected_context):
                st.sidebar.success(f"Switched to context {selected_context}")
            else:
                st.sidebar.error(f"Failed to switch to context {selected_context}")
                return None, None, None, False, None
    
    # Namespace selection
    namespaces = k8s_client.get_namespaces()
    
    if not namespaces:
        st.sidebar.warning("No namespaces found or access denied")
        return selected_context, None, None, False, None
    
    # Add "all-namespaces" option for future use
    # namespaces.insert(0, "all-namespaces")
    
    selected_namespace = st.sidebar.selectbox(
        "Namespace",
        options=namespaces,
        help="Select the namespace to analyze"
    )
    
    # Analysis type selection
    analysis_type = st.sidebar.radio(
        "Analysis Type",
        options=[
            "comprehensive",
            "metrics",
            "logs",
            "traces",
            "topology",
            "events"
        ],
        help=(
            "Comprehensive: Run all specialized agents\n"
            "Metrics: Resource usage and performance\n"
            "Logs: Container logs analysis\n"
            "Traces: Distributed tracing analysis\n"
            "Topology: Service dependencies and networking\n"
            "Events: Kubernetes events analysis"
        )
    )
    
    # Analysis scope and depth settings
    st.sidebar.subheader("Analysis Settings")
    
    # Problem description for the LLM agents
    problem_description = st.sidebar.text_area(
        "Problem Description (optional)",
        placeholder="Describe the issue you're experiencing, e.g., 'High latency in the payment service' or 'Pods are frequently restarting'",
        help="Providing a description helps the LLM agents focus their analysis on specific areas"
    )
    
    # If needed, add settings to control analysis depth
    # analysis_depth = st.sidebar.slider("Analysis Depth", min_value=1, max_value=5, value=3, 
    #                                  help="Higher values mean more thorough analysis but take longer")
    
    # Include pods with specific labels
    # pod_label_filter = st.sidebar.text_input("Pod Label Selector (optional)", 
    #                                        help="e.g., app=myapp,tier=frontend")
    
    # Button to start analysis
    submitted = st.sidebar.button("Run Analysis", type="primary")
    
    # Disclaimer
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "This tool analyzes your Kubernetes resources and does not make any changes to your cluster. "
        "All analysis is read-only."
    )
    
    # Show current connection info
    st.sidebar.markdown("---")
    st.sidebar.subheader("Connection Info")
    st.sidebar.text(f"Context: {selected_context}")
    st.sidebar.text(f"Namespace: {selected_namespace}")
    
    return selected_context, selected_namespace, analysis_type, submitted, problem_description
