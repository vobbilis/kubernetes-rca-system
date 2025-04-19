import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import yaml
import time
import os
import json
from agent_coordinator import AgentCoordinator
from utils.kubernetes_client import KubernetesClient
from utils.visualization import (
    visualize_topology, 
    visualize_metrics, 
    visualize_traces,
    plot_reasoning_process
)

# Set page config
st.set_page_config(
    page_title="K8s Root Cause Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'analysis_started' not in st.session_state:
    st.session_state.analysis_started = False
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'k8s_client' not in st.session_state:
    st.session_state.k8s_client = None
if 'agent_coordinator' not in st.session_state:
    st.session_state.agent_coordinator = None
if 'selected_namespace' not in st.session_state:
    st.session_state.selected_namespace = None
if 'reasoning_process' not in st.session_state:
    st.session_state.reasoning_process = []
if 'analysis_summary' not in st.session_state:
    st.session_state.analysis_summary = None
if 'current_tab' not in st.session_state:
    st.session_state.current_tab = "Dashboard"

# Title and description
st.title("Kubernetes Root Cause Analysis")
st.markdown("""
This tool helps identify and analyze issues in your Kubernetes cluster using a multi-agent system.
Each specialized agent analyzes different aspects of your cluster, including metrics, logs, traces, topology, and events.
""")

# Sidebar
with st.sidebar:
    st.header("Configuration")
    
    # Connection config
    with st.expander("Kubernetes Connection", expanded=True):
        connection_method = st.radio(
            "Connection Method",
            options=["Current Context", "Custom Config"],
            index=0
        )
        
        if connection_method == "Custom Config":
            kubeconfig_path = st.text_input("Kubeconfig Path", value="~/.kube/config")
            context_name = st.text_input("Context Name (optional)")
        else:
            kubeconfig_path = "~/.kube/config"
            context_name = None
    
    # Connect to Kubernetes
    if st.button("Connect to Cluster"):
        with st.spinner("Connecting to Kubernetes cluster..."):
            try:
                st.session_state.k8s_client = KubernetesClient(
                    kubeconfig_path=os.path.expanduser(kubeconfig_path),
                    context=context_name if connection_method == "Custom Config" else None
                )
                
                # Initialize agent coordinator
                st.session_state.agent_coordinator = AgentCoordinator(st.session_state.k8s_client)
                
                st.success("Successfully connected to Kubernetes cluster!")
                
                # Get available namespaces
                namespaces = st.session_state.k8s_client.get_namespaces()
                if namespaces:
                    st.session_state.selected_namespace = namespaces[0]
            except Exception as e:
                st.error(f"Failed to connect to Kubernetes cluster: {str(e)}")
    
    if st.session_state.k8s_client:
        # Display cluster info
        st.subheader("Cluster Info")
        cluster_info = st.session_state.k8s_client.get_cluster_info()
        st.info(f"Cluster: {cluster_info['name']}\nVersion: {cluster_info['version']}")
        
        # Namespace selection
        namespaces = st.session_state.k8s_client.get_namespaces()
        st.session_state.selected_namespace = st.selectbox(
            "Select Namespace",
            options=namespaces,
            index=namespaces.index(st.session_state.selected_namespace) if st.session_state.selected_namespace in namespaces else 0
        )
    
    # Navigation
    st.header("Navigation")
    tabs = ["Dashboard", "Analysis", "Results", "Settings"]
    for tab in tabs:
        if st.button(tab, key=f"nav_{tab}"):
            st.session_state.current_tab = tab
            st.rerun()

# Main content area based on selected tab
if st.session_state.current_tab == "Dashboard":
    if st.session_state.k8s_client:
        st.header("Cluster Overview")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Node Status")
            nodes = st.session_state.k8s_client.get_nodes()
            if nodes:
                nodes_df = pd.DataFrame(nodes)
                fig = px.pie(
                    names=nodes_df['status'].value_counts().index,
                    values=nodes_df['status'].value_counts().values,
                    title="Node Status",
                    color_discrete_sequence=px.colors.qualitative.Plotly
                )
                st.plotly_chart(fig)
            else:
                st.info("No node information available")
        
        with col2:
            st.subheader("Pod Status")
            pods = st.session_state.k8s_client.get_pods(namespace=st.session_state.selected_namespace)
            if pods:
                pods_df = pd.DataFrame(pods)
                fig = px.pie(
                    names=pods_df['status'].value_counts().index,
                    values=pods_df['status'].value_counts().values,
                    title=f"Pod Status in {st.session_state.selected_namespace}",
                    color_discrete_sequence=px.colors.qualitative.Plotly
                )
                st.plotly_chart(fig)
            else:
                st.info(f"No pods found in namespace {st.session_state.selected_namespace}")
        
        st.subheader("Resources")
        
        tabs = st.tabs(["Pods", "Deployments", "Services"])
        
        with tabs[0]:
            if pods:
                st.dataframe(pods_df[['name', 'status', 'containers', 'restarts', 'age']])
            else:
                st.info(f"No pods found in namespace {st.session_state.selected_namespace}")
        
        with tabs[1]:
            deployments = st.session_state.k8s_client.get_deployments(namespace=st.session_state.selected_namespace)
            if deployments:
                deployments_df = pd.DataFrame(deployments)
                st.dataframe(deployments_df[['name', 'ready', 'up_to_date', 'available', 'age']])
            else:
                st.info(f"No deployments found in namespace {st.session_state.selected_namespace}")
        
        with tabs[2]:
            services = st.session_state.k8s_client.get_services(namespace=st.session_state.selected_namespace)
            if services:
                services_df = pd.DataFrame(services)
                st.dataframe(services_df[['name', 'type', 'cluster_ip', 'external_ip', 'ports', 'age']])
            else:
                st.info(f"No services found in namespace {st.session_state.selected_namespace}")
    else:
        st.info("Please connect to a Kubernetes cluster using the sidebar configuration")

elif st.session_state.current_tab == "Analysis":
    st.header("Root Cause Analysis")
    
    if not st.session_state.k8s_client:
        st.warning("Please connect to a Kubernetes cluster first")
    else:
        st.markdown("""
        Configure your analysis by selecting the components to analyze and entering the issue description.
        The multi-agent system will analyze different aspects of your Kubernetes cluster to identify potential issues.
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Analysis Configuration")
            
            # Analysis scope
            st.write("Analysis Scope")
            
            namespace = st.selectbox(
                "Namespace",
                options=st.session_state.k8s_client.get_namespaces(),
                index=st.session_state.k8s_client.get_namespaces().index(st.session_state.selected_namespace) 
                    if st.session_state.selected_namespace in st.session_state.k8s_client.get_namespaces() else 0
            )
            
            resource_type = st.selectbox(
                "Resource Type",
                options=["All", "Pod", "Deployment", "Service", "StatefulSet", "Node"]
            )
            
            if resource_type != "All" and resource_type != "Node":
                resources = st.session_state.k8s_client.get_resources_by_type(
                    resource_type.lower(), namespace
                )
                resource_name = st.selectbox(
                    "Resource Name", 
                    options=["All"] + [r["name"] for r in resources]
                )
            else:
                resource_name = "All"
            
            time_range = st.select_slider(
                "Time Range",
                options=["Last 15 minutes", "Last hour", "Last 3 hours", "Last 12 hours", "Last 24 hours"],
                value="Last hour"
            )
            
            # Agent selection
            st.write("Agents to Use")
            use_metrics_agent = st.checkbox("Metrics Agent (CPU, Memory, Network)", value=True)
            use_logs_agent = st.checkbox("Logs Agent (Container Logs)", value=True)
            use_traces_agent = st.checkbox("Traces Agent (Request Path)", value=True)
            use_topology_agent = st.checkbox("Topology Agent (Dependencies)", value=True)
            use_events_agent = st.checkbox("Events Agent (Cluster Events)", value=True)
            
            # Issue description
            issue_description = st.text_area(
                "Issue Description",
                placeholder="Describe the issue you're experiencing with your Kubernetes application...",
                height=100
            )
        
        with col2:
            st.subheader("Analysis Priority")
            st.write("Rank the importance of different analysis aspects")
            
            metrics_priority = st.slider("Metrics Importance", 1, 5, 3)
            logs_priority = st.slider("Logs Importance", 1, 5, 3)
            traces_priority = st.slider("Traces Importance", 1, 5, 3)
            topology_priority = st.slider("Topology Importance", 1, 5, 3)
            events_priority = st.slider("Events Importance", 1, 5, 3)
        
        # Start analysis button
        start_analysis = st.button("Start Root Cause Analysis")
        
        if start_analysis:
            if not issue_description and resource_type == "All" and resource_name == "All":
                st.error("Please provide an issue description or select specific resources to analyze")
            else:
                st.session_state.analysis_started = True
                
                # Configure analysis settings
                analysis_config = {
                    "namespace": namespace,
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "time_range": time_range,
                    "issue_description": issue_description,
                    "agents": {
                        "metrics": {"use": use_metrics_agent, "priority": metrics_priority},
                        "logs": {"use": use_logs_agent, "priority": logs_priority},
                        "traces": {"use": use_traces_agent, "priority": traces_priority},
                        "topology": {"use": use_topology_agent, "priority": topology_priority},
                        "events": {"use": use_events_agent, "priority": events_priority}
                    }
                }
                
                # Show progress
                progress_text = "Running analysis..."
                progress_bar = st.progress(0, text=progress_text)
                
                # Initialize tracking variables
                steps = 5  # Total number of analysis steps
                current_step = 0
                
                # Initialize reasoning process
                st.session_state.reasoning_process = []
                
                # Execute analysis
                try:
                    # Update progress
                    current_step += 1
                    progress_bar.progress(current_step/steps, text=f"{progress_text} Collecting data...")
                    
                    # Step 1: Initialize analysis
                    coordinator = st.session_state.agent_coordinator
                    analysis_id = coordinator.init_analysis(analysis_config)
                    
                    # Step 2: Run core analysis
                    current_step += 1
                    progress_bar.progress(current_step/steps, text=f"{progress_text} Analyzing metrics and logs...")
                    
                    # Collect core data
                    if use_metrics_agent:
                        metrics_results = coordinator.run_metrics_analysis(analysis_id)
                        st.session_state.reasoning_process.append({
                            "agent": "Metrics Agent",
                            "findings": metrics_results["findings"],
                            "conclusion": metrics_results["conclusion"]
                        })
                    
                    if use_logs_agent:
                        logs_results = coordinator.run_logs_analysis(analysis_id)
                        st.session_state.reasoning_process.append({
                            "agent": "Logs Agent",
                            "findings": logs_results["findings"],
                            "conclusion": logs_results["conclusion"]
                        })
                    
                    # Step 3: Run additional analysis
                    current_step += 1
                    progress_bar.progress(current_step/steps, text=f"{progress_text} Analyzing topology and events...")
                    
                    if use_topology_agent:
                        topology_results = coordinator.run_topology_analysis(analysis_id)
                        st.session_state.reasoning_process.append({
                            "agent": "Topology Agent",
                            "findings": topology_results["findings"],
                            "conclusion": topology_results["conclusion"]
                        })
                    
                    if use_events_agent:
                        events_results = coordinator.run_events_analysis(analysis_id)
                        st.session_state.reasoning_process.append({
                            "agent": "Events Agent",
                            "findings": events_results["findings"],
                            "conclusion": events_results["conclusion"]
                        })
                    
                    if use_traces_agent:
                        traces_results = coordinator.run_traces_analysis(analysis_id)
                        st.session_state.reasoning_process.append({
                            "agent": "Traces Agent",
                            "findings": traces_results["findings"],
                            "conclusion": traces_results["conclusion"]
                        })
                    
                    # Step 4: Coordinate results
                    current_step += 1
                    progress_bar.progress(current_step/steps, text=f"{progress_text} Correlating findings...")
                    
                    final_results = coordinator.correlate_findings(analysis_id)
                    
                    # Step 5: Finalize analysis
                    current_step += 1
                    progress_bar.progress(current_step/steps, text="Analysis complete!")
                    
                    # Store results
                    st.session_state.analysis_results = final_results
                    st.session_state.analysis_summary = coordinator.generate_summary(analysis_id)
                    
                    # Display success and navigation to results
                    st.success("Root cause analysis completed successfully!")
                    st.button("View Results", on_click=lambda: setattr(st.session_state, 'current_tab', 'Results'))
                
                except Exception as e:
                    st.error(f"Analysis failed: {str(e)}")
                finally:
                    if current_step < steps:
                        progress_bar.progress(1.0, text="Analysis finished")

elif st.session_state.current_tab == "Results":
    st.header("Analysis Results")
    
    if not st.session_state.analysis_results:
        st.info("No analysis results available. Run an analysis first.")
    else:
        results = st.session_state.analysis_results
        summary = st.session_state.analysis_summary
        
        # Summary and root causes
        st.subheader("Root Cause Analysis Summary")
        
        if summary:
            st.markdown(f"**Issue**: {summary['issue_description']}")
            
            st.write("**Identified Root Causes:**")
            for idx, cause in enumerate(summary['root_causes'], 1):
                st.markdown(f"**{idx}. {cause['title']}**")
                st.markdown(f"- **Severity**: {cause['severity']}")
                st.markdown(f"- **Description**: {cause['description']}")
                st.markdown(f"- **Evidence**: {cause['evidence']}")
            
            st.write("**Recommendations:**")
            for idx, rec in enumerate(summary['recommendations'], 1):
                st.markdown(f"**{idx}. {rec['title']}**")
                st.markdown(f"- {rec['description']}")
        else:
            st.info("No summary available")
        
        # Tabs for different result types
        result_tabs = st.tabs(["Metrics", "Logs", "Topology", "Events", "Traces", "Reasoning Process"])
        
        # Metrics results
        with result_tabs[0]:
            st.subheader("Metrics Analysis")
            if 'metrics' in results and results['metrics']:
                metrics_data = results['metrics']
                
                # Show resource usage
                if 'resource_usage' in metrics_data:
                    st.write("Resource Usage:")
                    visualize_metrics(metrics_data['resource_usage'])
                
                # Show anomalies
                if 'anomalies' in metrics_data and metrics_data['anomalies']:
                    st.write("Detected Anomalies:")
                    for anomaly in metrics_data['anomalies']:
                        st.warning(f"**{anomaly['resource']}**: {anomaly['description']}")
                        if 'chart_data' in anomaly:
                            fig = px.line(
                                anomaly['chart_data'], 
                                x='timestamp', 
                                y='value',
                                title=f"{anomaly['resource']} Anomaly"
                            )
                            st.plotly_chart(fig)
                else:
                    st.success("No metric anomalies detected")
            else:
                st.info("No metrics data available")
        
        # Logs results
        with result_tabs[1]:
            st.subheader("Logs Analysis")
            if 'logs' in results and results['logs']:
                logs_data = results['logs']
                
                # Show error patterns
                if 'error_patterns' in logs_data and logs_data['error_patterns']:
                    st.write("Detected Error Patterns:")
                    for pattern in logs_data['error_patterns']:
                        st.error(f"**{pattern['pattern']}** - Occurrences: {pattern['count']}")
                        
                        if 'examples' in pattern and pattern['examples']:
                            with st.expander("View examples"):
                                for example in pattern['examples']:
                                    st.code(example, language="bash")
                else:
                    st.success("No significant error patterns detected in logs")
                
                # Show log timeline
                if 'timeline' in logs_data and logs_data['timeline']:
                    st.write("Log Timeline:")
                    logs_df = pd.DataFrame(logs_data['timeline'])
                    fig = px.scatter(
                        logs_df, 
                        x='timestamp', 
                        y='severity',
                        color='severity',
                        size='count',
                        hover_data=['message'],
                        title="Log Events Timeline"
                    )
                    st.plotly_chart(fig)
            else:
                st.info("No logs analysis data available")
        
        # Topology results
        with result_tabs[2]:
            st.subheader("Topology Analysis")
            if 'topology' in results and results['topology']:
                topo_data = results['topology']
                
                # Show service map
                if 'service_map' in topo_data:
                    st.write("Service Dependency Map:")
                    visualize_topology(topo_data['service_map'])
                
                # Show issues
                if 'issues' in topo_data and topo_data['issues']:
                    st.write("Detected Topology Issues:")
                    for issue in topo_data['issues']:
                        st.error(f"**{issue['title']}**")
                        st.markdown(f"- **Type**: {issue['type']}")
                        st.markdown(f"- **Description**: {issue['description']}")
                        if 'affected_services' in issue:
                            st.markdown("- **Affected Services**: " + ", ".join(issue['affected_services']))
                else:
                    st.success("No topology issues detected")
            else:
                st.info("No topology data available")
        
        # Events results
        with result_tabs[3]:
            st.subheader("Events Analysis")
            if 'events' in results and results['events']:
                events_data = results['events']
                
                # Show critical events
                if 'critical_events' in events_data and events_data['critical_events']:
                    st.write("Critical Events:")
                    events_df = pd.DataFrame(events_data['critical_events'])
                    st.dataframe(events_df)
                else:
                    st.success("No critical events detected")
                
                # Show event timeline
                if 'timeline' in events_data and events_data['timeline']:
                    st.write("Event Timeline:")
                    events_timeline = pd.DataFrame(events_data['timeline'])
                    fig = px.timeline(
                        events_timeline, 
                        x_start='start_time', 
                        x_end='end_time', 
                        y='component',
                        color='event_type',
                        hover_data=['description'],
                        title="Cluster Events Timeline"
                    )
                    st.plotly_chart(fig)
            else:
                st.info("No events data available")
        
        # Traces results
        with result_tabs[4]:
            st.subheader("Traces Analysis")
            if 'traces' in results and results['traces']:
                traces_data = results['traces']
                
                # Show latency issues
                if 'latency_issues' in traces_data and traces_data['latency_issues']:
                    st.write("Latency Issues:")
                    for issue in traces_data['latency_issues']:
                        st.warning(f"**{issue['service']}**: {issue['description']}")
                else:
                    st.success("No significant latency issues detected")
                
                # Show trace visualization
                if 'trace_map' in traces_data:
                    st.write("Request Flow Visualization:")
                    visualize_traces(traces_data['trace_map'])
            else:
                st.info("No traces data available")
        
        # Reasoning process
        with result_tabs[5]:
            st.subheader("Agent Reasoning Process")
            if st.session_state.reasoning_process:
                plot_reasoning_process(st.session_state.reasoning_process)
                
                st.write("Detailed Reasoning Steps:")
                for idx, step in enumerate(st.session_state.reasoning_process, 1):
                    with st.expander(f"Step {idx}: {step['agent']} Analysis"):
                        st.write("**Findings:**")
                        for finding in step['findings']:
                            st.markdown(f"- {finding}")
                        
                        st.write("**Conclusion:**")
                        st.markdown(step['conclusion'])
            else:
                st.info("No reasoning process data available")

elif st.session_state.current_tab == "Settings":
    st.header("Settings")
    
    with st.expander("Kubernetes API Settings", expanded=True):
        st.write("Configure how the tool interacts with the Kubernetes API")
        
        timeout = st.slider("API Timeout (seconds)", 10, 120, 30)
        batch_size = st.slider("Batch Size for Large Queries", 50, 500, 100)
        
        st.write("Proxy Configuration (if needed)")
        use_proxy = st.checkbox("Use Proxy")
        if use_proxy:
            proxy_url = st.text_input("Proxy URL")
            
        cache_ttl = st.slider("Cache TTL (minutes)", 1, 60, 15)
        
        if st.button("Save API Settings"):
            # These settings would be saved to the client in a real implementation
            st.success("API settings saved successfully")
    
    with st.expander("Analysis Settings"):
        st.write("Configure default analysis parameters")
        
        default_time_range = st.select_slider(
            "Default Time Range",
            options=["Last 15 minutes", "Last hour", "Last 3 hours", "Last 12 hours", "Last 24 hours"],
            value="Last hour"
        )
        
        max_log_entries = st.number_input("Maximum Log Entries to Process", 100, 10000, 1000)
        detection_sensitivity = st.slider("Anomaly Detection Sensitivity", 0.1, 5.0, 2.0, 0.1)
        correlation_threshold = st.slider("Event Correlation Threshold", 0.1, 1.0, 0.7, 0.05)
        
        if st.button("Save Analysis Settings"):
            st.success("Analysis settings saved successfully")
    
    with st.expander("Visualization Settings"):
        st.write("Configure how data is displayed")
        
        chart_theme = st.selectbox(
            "Chart Theme",
            options=["Default", "Light", "Dark", "Presentation"]
        )
        
        color_blind_mode = st.checkbox("Color Blind Friendly Mode")
        show_confidence = st.checkbox("Show Confidence Intervals", value=True)
        
        if st.button("Save Visualization Settings"):
            st.success("Visualization settings saved successfully")
