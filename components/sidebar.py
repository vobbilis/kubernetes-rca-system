import streamlit as st
from utils.db_handler import DBHandler

def render_sidebar(k8s_client):
    """
    Render the sidebar for the Kubernetes root cause analysis application.
    
    Args:
        k8s_client: Instance of the Kubernetes client
        
    Returns:
        tuple: (selected_context, selected_namespace, analysis_type, submitted, problem_description, selected_investigation)
    """
    st.sidebar.title("K8s Root Cause Analysis")
    
    # Initialize session state for investigation
    if 'current_investigation_id' not in st.session_state:
        st.session_state['current_investigation_id'] = None
    if 'db_handler' not in st.session_state:
        st.session_state['db_handler'] = DBHandler()
    
    # Tabs for Investigations and Configuration
    tab_investigations, tab_configuration = st.sidebar.tabs(["Investigations", "Configuration"])
    
    # Investigations Tab
    with tab_investigations:
        db_handler = st.session_state['db_handler']
        investigations = db_handler.list_investigations()
        
        # New Investigation button
        col1, col2 = st.columns([3, 1])
        with col1:
            new_investigation = st.button("➕ New Investigation", type="primary", key="sidebar_new_investigation")
        
        if new_investigation:
            st.session_state['current_investigation_id'] = None
            st.session_state['new_investigation'] = True
            # We need to directly switch to the configuration view
            # Force a rerun to refresh the UI
            st.rerun()
            
        # List of investigations
        st.subheader("Past Investigations")
        
        if not investigations:
            st.info("No previous investigations found.")
        else:
            # Display each investigation with a clickable card
            for inv in investigations:
                inv_id = inv.get("id")
                title = inv.get("title", "Untitled Investigation")
                namespace = inv.get("namespace", "unknown")
                status = inv.get("status", "unknown")
                created_at = inv.get("created_at", "")
                summary = inv.get("summary", "No summary available")
                
                # Create a card-like display for each investigation
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Truncate summary for display
                    display_summary = summary[:100] + "..." if len(summary) > 100 else summary
                    
                    # Format the display
                    st.markdown(f"**{title}**")
                    st.caption(f"Namespace: {namespace} | Created: {created_at}")
                    st.text(display_summary)
                
                with col2:
                    # Show status and provide button to view
                    status_color = "green" if status == "completed" else "blue"
                    st.markdown(f"<span style='color:{status_color}'>{status.upper()}</span>", unsafe_allow_html=True)
                    if st.button("View", key=f"view_{inv_id}"):
                        st.session_state['current_investigation_id'] = inv_id
                        # Force a rerun to refresh the UI
                        st.rerun()
                
                st.markdown("---")
    
    # Configuration Tab
    with tab_configuration:
        # Check if connected to Kubernetes
        if not k8s_client.is_connected():
            st.warning("⚠️ Not connected to Kubernetes")
            st.info("Please configure kubectl access to your cluster")
            return None, None, None, False, None, None
        
        # Kubernetes context selection
        available_contexts = k8s_client.get_available_contexts()
        current_context = k8s_client.get_current_context()
        
        selected_context = st.selectbox(
            "Kubernetes Context",
            options=available_contexts,
            index=available_contexts.index(current_context) if current_context in available_contexts else 0,
            help="Select the Kubernetes context to analyze"
        )
        
        # Change context if needed
        if selected_context != current_context:
            with st.spinner(f"Switching to context {selected_context}..."):
                if k8s_client.set_context(selected_context):
                    st.success(f"Switched to context {selected_context}")
                else:
                    st.error(f"Failed to switch to context {selected_context}")
                    return None, None, None, False, None, None
        
        # Namespace selection
        namespaces = k8s_client.get_namespaces()
        
        if not namespaces:
            st.warning("No namespaces found or access denied")
            return selected_context, None, None, False, None, None
        
        selected_namespace = st.selectbox(
            "Namespace",
            options=namespaces,
            help="Select the namespace to analyze"
        )
        
        # Analysis type selection
        analysis_type = st.radio(
            "Analysis Type",
            options=[
                "comprehensive",
                "resources",
                "metrics",
                "logs",
                "traces",
                "topology",
                "events"
            ],
            help=(
                "Comprehensive: Run all specialized agents\n"
                "Resources: Basic Kubernetes resource health check\n"
                "Metrics: Resource usage and performance\n"
                "Logs: Container logs analysis\n"
                "Traces: Distributed tracing analysis\n"
                "Topology: Service dependencies and networking\n"
                "Events: Kubernetes events analysis"
            )
        )
        
        # Investigation title
        investigation_title = st.text_input(
            "Investigation Title",
            placeholder="Enter a descriptive title for this investigation",
            help="A title that helps you identify this investigation later"
        )
        
        # Problem description for the LLM agents
        problem_description = st.text_area(
            "Problem Description",
            placeholder="Describe the issue you're experiencing, e.g., 'High latency in the payment service' or 'Pods are frequently restarting'",
            help="Providing a description helps the LLM agents focus their analysis on specific areas"
        )
        
        # Button to start analysis
        submitted = st.button("Start Investigation", type="primary")
        
        if submitted:
            if not investigation_title:
                st.error("Please provide a title for the investigation")
                submitted = False
            else:
                # Create a new investigation
                investigation_id = st.session_state['db_handler'].create_investigation(
                    title=investigation_title,
                    namespace=selected_namespace,
                    context=problem_description
                )
                st.session_state['current_investigation_id'] = investigation_id
                
                # Add initial message
                st.session_state['db_handler'].add_conversation_entry(
                    investigation_id=investigation_id,
                    role="system",
                    content=f"Investigation started for namespace {selected_namespace}. Analysis type: {analysis_type}."
                )
                
                # Add user problem description if provided
                if problem_description:
                    st.session_state['db_handler'].add_conversation_entry(
                        investigation_id=investigation_id,
                        role="user",
                        content=problem_description
                    )
    
    # Show current connection info at the bottom of the sidebar
    st.sidebar.markdown("---")
    st.sidebar.caption("Connection Info")
    st.sidebar.text(f"Context: {selected_context}")
    st.sidebar.text(f"Namespace: {selected_namespace}")
    
    # Disclaimer
    st.sidebar.caption(
        "This tool analyzes your Kubernetes resources and does not make any changes to your cluster. "
        "All analysis is read-only."
    )
    
    # Return the current investigation ID along with other values
    return (
        selected_context, 
        selected_namespace, 
        analysis_type, 
        submitted, 
        problem_description, 
        st.session_state.get('current_investigation_id')
    )
