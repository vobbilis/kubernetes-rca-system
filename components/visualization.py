import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx
import pandas as pd
from collections import Counter

def render_visualization(analysis_results, analysis_type):
    """
    Render visualizations for the analysis results.
    
    Args:
        analysis_results: Results from the analysis
        analysis_type: Type of analysis that was performed
    """
    st.header("📊 Analysis Visualization")
    
    if 'error' in analysis_results:
        st.error(f"Error during analysis: {analysis_results['error']}")
        return
    
    # Show different visualizations based on analysis type
    if analysis_type == 'comprehensive':
        _render_comprehensive_visualizations(analysis_results)
    elif analysis_type == 'metrics':
        _render_metrics_visualizations(analysis_results)
    elif analysis_type == 'logs':
        _render_logs_visualizations(analysis_results)
    elif analysis_type == 'traces':
        _render_traces_visualizations(analysis_results)
    elif analysis_type == 'topology':
        _render_topology_visualizations(analysis_results)
    elif analysis_type == 'events':
        _render_events_visualizations(analysis_results)
    else:
        st.warning(f"No visualizations available for analysis type: {analysis_type}")

def _render_comprehensive_visualizations(results):
    """
    Render visualizations for comprehensive analysis results.
    
    Args:
        results: Comprehensive analysis results
    """
    # Extract findings from all agents
    all_findings = []
    agent_names = []
    
    for agent_name, agent_results in results.get('agent_results', {}).items():
        findings = agent_results.get('findings', [])
        if findings:
            all_findings.extend(findings)
            agent_names.extend([agent_name] * len(findings))
    
    if not all_findings:
        st.info("No findings to visualize. Your cluster looks healthy!")
        return
    
    # Create a DataFrame for the findings
    findings_df = pd.DataFrame({
        'component': [f.get('component', 'Unknown') for f in all_findings],
        'issue': [f.get('issue', 'Unknown issue') for f in all_findings],
        'severity': [f.get('severity', 'info') for f in all_findings],
        'agent': agent_names
    })
    
    # Display findings by severity
    st.subheader("Findings by Severity")
    
    # Count findings by severity
    severity_counts = findings_df['severity'].value_counts().reset_index()
    severity_counts.columns = ['severity', 'count']
    
    # Define severity order for consistent colors
    severity_order = ['critical', 'high', 'medium', 'low', 'info']
    severity_counts['severity_rank'] = severity_counts['severity'].apply(lambda x: severity_order.index(x) if x in severity_order else 999)
    severity_counts = severity_counts.sort_values('severity_rank')
    
    # Create bar chart
    fig = px.bar(
        severity_counts, 
        x='severity', 
        y='count',
        color='severity',
        color_discrete_map={
            'critical': '#FF0000',
            'high': '#FF6B6B',
            'medium': '#FFAC4B',
            'low': '#4B93FF',
            'info': '#6BCB77'
        },
        labels={'severity': 'Severity', 'count': 'Number of Findings'},
        title='Distribution of Findings by Severity'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display findings by agent
    st.subheader("Findings by Agent")
    
    # Count findings by agent
    agent_counts = findings_df['agent'].value_counts().reset_index()
    agent_counts.columns = ['agent', 'count']
    
    # Create bar chart
    fig = px.bar(
        agent_counts, 
        x='agent', 
        y='count',
        labels={'agent': 'Agent', 'count': 'Number of Findings'},
        title='Distribution of Findings by Agent',
        color='agent'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # If there are root causes identified, visualize them
    root_causes = results.get('root_causes', [])
    if root_causes:
        st.subheader("Root Causes Analysis")
        
        # Create a table for the root causes
        root_cause_df = pd.DataFrame({
            'component': [rc.get('component', 'Unknown') for rc in root_causes],
            'related_findings_count': [rc.get('related_findings_count', 0) for rc in root_causes],
            'severity': [rc.get('severity', 'Unknown') for rc in root_causes]
        })
        
        # Display the table
        st.dataframe(root_cause_df, use_container_width=True)
    
    # If there are correlated findings, visualize them
    correlated_findings = results.get('correlated_findings', [])
    if correlated_findings:
        st.subheader("Correlated Issues")
        
        # Visualize correlations as a network graph
        G = nx.Graph()
        
        # Add nodes for components
        components = set()
        for finding in correlated_findings:
            component = finding.get('component', 'Unknown')
            components.add(component)
            G.add_node(component, type='component')
            
            # Add related findings as nodes and connect to component
            related_findings = finding.get('related_findings', [])
            for i, related in enumerate(related_findings):
                issue = related.get('issue', 'Unknown issue')
                node_id = f"{component}_issue_{i}"
                G.add_node(node_id, type='issue', label=issue, severity=related.get('severity', 'info'))
                G.add_edge(component, node_id)
        
        # Add edges between components that share issues
        component_issues = {}
        for finding in correlated_findings:
            component = finding.get('component', 'Unknown')
            related_findings = finding.get('related_findings', [])
            issues = [f.get('issue', '') for f in related_findings]
            component_issues[component] = set(issues)
        
        for comp1 in components:
            for comp2 in components:
                if comp1 != comp2:
                    common_issues = component_issues.get(comp1, set()) & component_issues.get(comp2, set())
                    if common_issues:
                        G.add_edge(comp1, comp2, weight=len(common_issues))
        
        # Use networkx to layout the graph
        pos = nx.spring_layout(G)
        
        # Create edge traces
        edge_trace = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_trace.append(
                go.Scatter(
                    x=[x0, x1, None],
                    y=[y0, y1, None],
                    mode='lines',
                    line=dict(width=0.5, color='#888'),
                    hoverinfo='none'
                )
            )
        
        # Create node traces
        node_trace_component = go.Scatter(
            x=[pos[node][0] for node in G.nodes() if G.nodes[node].get('type') == 'component'],
            y=[pos[node][1] for node in G.nodes() if G.nodes[node].get('type') == 'component'],
            mode='markers',
            marker=dict(
                size=15,
                color='blue',
                line=dict(width=2)
            ),
            text=[node for node in G.nodes() if G.nodes[node].get('type') == 'component'],
            hoverinfo='text'
        )
        
        # Create a trace for each severity level
        severity_traces = {}
        for severity in ['critical', 'high', 'medium', 'low', 'info']:
            nodes = [node for node in G.nodes() if G.nodes[node].get('type') == 'issue' and G.nodes[node].get('severity') == severity]
            if nodes:
                severity_traces[severity] = go.Scatter(
                    x=[pos[node][0] for node in nodes],
                    y=[pos[node][1] for node in nodes],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color={'critical': 'red', 'high': '#FF6B6B', 'medium': '#FFAC4B', 'low': '#4B93FF', 'info': '#6BCB77'}[severity],
                        line=dict(width=1)
                    ),
                    text=[G.nodes[node].get('label', '') for node in nodes],
                    hoverinfo='text',
                    name=severity
                )
        
        # Create the figure
        fig = go.Figure(
            data=edge_trace + [node_trace_component] + list(severity_traces.values()),
            layout=go.Layout(
                title='Correlation between Components and Issues',
                showlegend=True,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)

def _render_metrics_visualizations(results):
    """
    Render visualizations for metrics analysis results.
    
    Args:
        results: Metrics analysis results
    """
    findings = results.get('findings', [])
    
    if not findings:
        st.info("No metrics issues found. Your resources look well-configured!")
        return
    
    # Group findings by component
    component_groups = {}
    for finding in findings:
        component = finding.get('component', 'Unknown')
        if component not in component_groups:
            component_groups[component] = []
        component_groups[component].append(finding)
    
    # Create a visualization for CPU and memory findings
    cpu_findings = [f for f in findings if 'CPU' in f.get('component', '')]
    memory_findings = [f for f in findings if 'Memory' in f.get('component', '')]
    
    if cpu_findings or memory_findings:
        st.subheader("Resource Usage Issues")
        
        # Extract pod names and usage values
        pods_with_issues = set()
        cpu_values = {}
        memory_values = {}
        
        for finding in cpu_findings:
            # Try to extract pod names and CPU values from the evidence
            evidence = finding.get('evidence', '')
            for line in evidence.split('\n'):
                if ': ' in line:
                    parts = line.split(': ')
                    if len(parts) >= 2:
                        pod_info = parts[1]
                        # Extract pod name and CPU percentage
                        match = re.search(r'(\S+) \((\d+\.\d+)%\)', pod_info)
                        if match:
                            pod_name = match.group(1)
                            cpu_percent = float(match.group(2))
                            pods_with_issues.add(pod_name)
                            cpu_values[pod_name] = cpu_percent
        
        for finding in memory_findings:
            # Try to extract pod names and memory values from the evidence
            evidence = finding.get('evidence', '')
            for line in evidence.split('\n'):
                if ': ' in line:
                    parts = line.split(': ')
                    if len(parts) >= 2:
                        pod_info = parts[1]
                        # Extract pod name and memory percentage
                        match = re.search(r'(\S+) \((\d+\.\d+)%\)', pod_info)
                        if match:
                            pod_name = match.group(1)
                            memory_percent = float(match.group(2))
                            pods_with_issues.add(pod_name)
                            memory_values[pod_name] = memory_percent
        
        # Create a DataFrame for the pod resource usage
        if pods_with_issues:
            data = []
            for pod in pods_with_issues:
                data.append({
                    'Pod': pod,
                    'CPU Usage (%)': cpu_values.get(pod, 0),
                    'Memory Usage (%)': memory_values.get(pod, 0)
                })
            
            df = pd.DataFrame(data)
            
            # Create a bar chart
            fig = go.Figure()
            
            if cpu_values:
                fig.add_trace(go.Bar(
                    x=df['Pod'],
                    y=df['CPU Usage (%)'],
                    name='CPU Usage (%)',
                    marker_color='#636EFA'
                ))
            
            if memory_values:
                fig.add_trace(go.Bar(
                    x=df['Pod'],
                    y=df['Memory Usage (%)'],
                    name='Memory Usage (%)',
                    marker_color='#EF553B'
                ))
            
            fig.update_layout(
                title='Pod Resource Usage with Issues',
                xaxis_title='Pod',
                yaxis_title='Usage (%)',
                barmode='group',
                yaxis=dict(range=[0, max(100, df['CPU Usage (%)'].max(), df['Memory Usage (%)'].max())])
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Visualize HPA issues if present
    hpa_findings = [f for f in findings if 'HPA' in f.get('component', '')]
    if hpa_findings:
        st.subheader("Horizontal Pod Autoscaler Issues")
        
        # Extract HPA names and issues
        hpa_names = []
        hpa_issues = []
        
        for finding in hpa_findings:
            component = finding.get('component', '')
            if '/' in component:
                hpa_name = component.split('/')[1]
                hpa_names.append(hpa_name)
                hpa_issues.append(finding.get('issue', 'Unknown issue'))
        
        # Create a DataFrame for the HPA issues
        if hpa_names:
            df = pd.DataFrame({
                'HPA': hpa_names,
                'Issue': hpa_issues
            })
            
            st.dataframe(df, use_container_width=True)
    
    # Visualize missing resource configurations
    resource_findings = [f for f in findings if 'Resource Configuration' in f.get('component', '')]
    if resource_findings:
        st.subheader("Resource Configuration Issues")
        
        for finding in resource_findings:
            st.warning(finding.get('issue', 'Resource configuration issue'))
            st.text(finding.get('evidence', ''))

def _render_logs_visualizations(results):
    """
    Render visualizations for logs analysis results.
    
    Args:
        results: Logs analysis results
    """
    findings = results.get('findings', [])
    
    if not findings:
        st.info("No log issues found. Your applications are running smoothly!")
        return
    
    # Group findings by their components
    component_groups = {}
    for finding in findings:
        component = finding.get('component', 'Unknown')
        if component not in component_groups:
            component_groups[component] = []
        component_groups[component].append(finding)
    
    # Create a sunburst chart for log issues by component and severity
    components = []
    parents = []
    values = []
    severities = []
    
    for component, comp_findings in component_groups.items():
        # Add the component as a root node
        components.append(component)
        parents.append("")
        values.append(len(comp_findings))
        severities.append("root")
        
        # Count findings by severity
        severity_counts = Counter(f.get('severity', 'info') for f in comp_findings)
        
        # Add severity nodes as children of the component
        for severity, count in severity_counts.items():
            components.append(f"{component}_{severity}")
            parents.append(component)
            values.append(count)
            severities.append(severity)
    
    # Create a sunburst chart
    if components:
        color_map = {
            'critical': '#FF0000',
            'high': '#FF6B6B',
            'medium': '#FFAC4B',
            'low': '#4B93FF',
            'info': '#6BCB77',
            'root': '#CCCCCC'
        }
        
        colors = [color_map.get(severity, '#CCCCCC') for severity in severities]
        
        fig = go.Figure(go.Sunburst(
            labels=components,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(colors=colors),
            hovertemplate='<b>%{label}</b><br>Issues: %{value}<br>',
            maxdepth=2
        ))
        
        fig.update_layout(
            margin=dict(t=0, l=0, r=0, b=0),
            title='Log Issues by Component and Severity'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Show a breakdown of error types
    error_types = []
    for finding in findings:
        issue = finding.get('issue', '')
        if 'Detected' in issue and 'instances of' in issue:
            # Extract error type from issues like "Detected X instances of <ErrorType> in logs"
            parts = issue.split('instances of')
            if len(parts) >= 2:
                error_type = parts[1].split('in logs')[0].strip()
                error_types.append(error_type)
    
    if error_types:
        error_counts = Counter(error_types)
        error_df = pd.DataFrame({
            'Error Type': list(error_counts.keys()),
            'Count': list(error_counts.values())
        }).sort_values('Count', ascending=False)
        
        # Create a bar chart
        fig = px.bar(
            error_df,
            x='Error Type',
            y='Count',
            title='Distribution of Error Types in Logs',
            color='Error Type'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Show container restart information
    restart_findings = [f for f in findings if 'restart' in f.get('issue', '').lower()]
    if restart_findings:
        st.subheader("Container Restarts")
        
        restart_data = []
        for finding in restart_findings:
            component = finding.get('component', 'Unknown')
            issue = finding.get('issue', 'Unknown issue')
            
            # Extract restart count from the issue
            restart_count = 0
            for word in issue.split():
                if word.isdigit():
                    restart_count = int(word)
                    break
            
            restart_data.append({
                'Container': component,
                'Restart Count': restart_count
            })
        
        if restart_data:
            restart_df = pd.DataFrame(restart_data)
            
            # Create a bar chart
            fig = px.bar(
                restart_df,
                x='Container',
                y='Restart Count',
                title='Container Restart Counts',
                color='Restart Count',
                color_continuous_scale=px.colors.sequential.Reds
            )
            
            st.plotly_chart(fig, use_container_width=True)

def _render_traces_visualizations(results):
    """
    Render visualizations for traces analysis results.
    
    Args:
        results: Traces analysis results
    """
    findings = results.get('findings', [])
    
    if not findings:
        st.info("No trace issues found or no tracing infrastructure detected.")
        
        # Check if we have a finding indicating no tracing platform
        for finding in findings:
            if 'No distributed tracing platform detected' in finding.get('issue', ''):
                st.warning("No distributed tracing platform detected in the cluster.")
                st.write(finding.get('recommendation', ''))
                break
        
        return
    
    # Group findings by component
    component_groups = {}
    for finding in findings:
        component = finding.get('component', 'Unknown')
        if component not in component_groups:
            component_groups[component] = []
        component_groups[component].append(finding)
    
    # Create service dependency visualization
    service_dependencies = []
    for finding in findings:
        component = finding.get('component', '')
        if '→' in component and 'Service' in component:
            component = component.replace('Service/', '')
            services = component.split('→')
            if len(services) >= 2:
                for i in range(len(services) - 1):
                    service_dependencies.append((services[i].strip(), services[i+1].strip()))
    
    if service_dependencies:
        st.subheader("Service Dependencies with Issues")
        
        # Create a directed graph
        G = nx.DiGraph()
        
        # Add edges for service dependencies
        for source, target in service_dependencies:
            G.add_edge(source, target)
        
        # Use networkx to layout the graph
        pos = nx.spring_layout(G)
        
        # Create edge traces
        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines')
        
        # Create node traces
        node_x = []
        node_y = []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=list(G.nodes()),
            textposition='top center',
            hoverinfo='text',
            marker=dict(
                showscale=False,
                color='#00BFFF',
                size=15,
                line=dict(width=2)
            )
        )
        
        # Create the figure
        fig = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title='Service Dependencies with Issues',
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Show latency issues
    latency_findings = [f for f in findings if 'latency' in f.get('issue', '').lower()]
    if latency_findings:
        st.subheader("Service Latency Issues")
        
        for finding in latency_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.warning(f"**{component}**: {issue}")
            st.text(evidence)
    
    # Show error rate issues
    error_findings = [f for f in findings if 'error' in f.get('issue', '').lower()]
    if error_findings:
        st.subheader("Service Error Issues")
        
        for finding in error_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.error(f"**{component}**: {issue}")
            st.text(evidence)

def _render_topology_visualizations(results):
    """
    Render visualizations for topology analysis results.
    
    Args:
        results: Topology analysis results
    """
    findings = results.get('findings', [])
    topology_data = results.get('topology_data', {})
    
    if not findings and not topology_data:
        st.info("No topology issues found or no topology data available.")
        return
    
    # If topology data is available, render a network graph
    if topology_data:
        nodes = topology_data.get('nodes', [])
        edges = topology_data.get('edges', [])
        
        if nodes and edges:
            st.subheader("Service Topology")
            
            # Create a directed graph
            G = nx.DiGraph()
            
            # Add nodes and edges
            for node in nodes:
                G.add_node(node['id'], type=node.get('type', 'unknown'))
            
            for edge in edges:
                G.add_edge(edge['source'], edge['target'], type=edge.get('type', 'unknown'))
            
            # Use networkx to layout the graph
            pos = nx.spring_layout(G)
            
            # Categorize nodes by type
            node_types = {}
            for node in nodes:
                node_type = node.get('type', 'unknown')
                if node_type not in node_types:
                    node_types[node_type] = []
                node_types[node_type].append(node['id'])
            
            # Define colors for node types
            node_colors = {
                'service': '#00BFFF',
                'deployment': '#FF6B6B',
                'ingress': '#FFAC4B',
                'configmap': '#6BCB77',
                'secret': '#9775FA',
                'unknown': '#CCCCCC'
            }
            
            # Create node traces for each type
            node_traces = []
            for node_type, node_ids in node_types.items():
                node_x = []
                node_y = []
                node_text = []
                
                for node_id in node_ids:
                    if node_id in pos:
                        x, y = pos[node_id]
                        node_x.append(x)
                        node_y.append(y)
                        node_text.append(node_id)
                
                node_traces.append(go.Scatter(
                    x=node_x, y=node_y,
                    mode='markers+text',
                    text=node_text,
                    textposition='top center',
                    textfont=dict(size=10),
                    hoverinfo='text',
                    name=node_type,
                    marker=dict(
                        color=node_colors.get(node_type, '#CCCCCC'),
                        size=15,
                        line=dict(width=1)
                    )
                ))
            
            # Create edge traces
            edge_x = []
            edge_y = []
            edge_text = []
            
            for edge in edges:
                source = edge['source']
                target = edge['target']
                edge_type = edge.get('type', 'unknown')
                
                if source in pos and target in pos:
                    x0, y0 = pos[source]
                    x1, y1 = pos[target]
                    edge_x.extend([x0, x1, None])
                    edge_y.extend([y0, y1, None])
                    edge_text.extend([edge_type, edge_type, None])
            
            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#888'),
                hoverinfo='none',
                mode='lines'
            )
            
            # Create the figure
            fig = go.Figure(
                data=[edge_trace] + node_traces,
                layout=go.Layout(
                    title='Service Topology',
                    showlegend=True,
                    hovermode='closest',
                    margin=dict(b=20, l=5, r=5, t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Group findings by type
    network_findings = [f for f in findings if 'Network' in f.get('component', '')]
    ingress_findings = [f for f in findings if 'Ingress' in f.get('component', '')]
    dependency_findings = [f for f in findings if 'Service Architecture' in f.get('component', '')]
    
    # Display network policy findings
    if network_findings:
        st.subheader("Network Policy Issues")
        
        for finding in network_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.warning(f"**{component}**: {issue}")
            st.text(evidence)
    
    # Display ingress findings
    if ingress_findings:
        st.subheader("Ingress Issues")
        
        for finding in ingress_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.warning(f"**{component}**: {issue}")
            st.text(evidence)
    
    # Display dependency findings
    if dependency_findings:
        st.subheader("Service Architecture Issues")
        
        for finding in dependency_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.warning(f"**{component}**: {issue}")
            st.text(evidence)

def _render_events_visualizations(results):
    """
    Render visualizations for events analysis results.
    
    Args:
        results: Events analysis results
    """
    findings = results.get('findings', [])
    
    if not findings:
        st.info("No event issues found. Your cluster looks stable!")
        return
    
    # Group findings by component type
    component_types = {}
    for finding in findings:
        component = finding.get('component', 'Unknown')
        component_type = component.split('/')[0] if '/' in component else component
        
        if component_type not in component_types:
            component_types[component_type] = []
        
        component_types[component_type].append(finding)
    
    # Create a pie chart of findings by component type
    component_counts = {comp_type: len(findings) for comp_type, findings in component_types.items()}
    
    fig = px.pie(
        values=list(component_counts.values()),
        names=list(component_counts.keys()),
        title='Event Issues by Component Type',
        hole=0.4
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Show findings by severity
    severities = [finding.get('severity', 'info') for finding in findings]
    severity_counts = Counter(severities)
    
    # Define severity order for consistent colors
    severity_order = ['critical', 'high', 'medium', 'low', 'info']
    severity_colors = {
        'critical': '#FF0000',
        'high': '#FF6B6B',
        'medium': '#FFAC4B',
        'low': '#4B93FF',
        'info': '#6BCB77'
    }
    
    # Create a sorted list of severities and counts
    sorted_severities = []
    sorted_counts = []
    for severity in severity_order:
        if severity in severity_counts:
            sorted_severities.append(severity)
            sorted_counts.append(severity_counts[severity])
    
    # Create a bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=sorted_severities,
            y=sorted_counts,
            marker_color=[severity_colors.get(s, '#CCCCCC') for s in sorted_severities]
        )
    ])
    
    fig.update_layout(
        title='Event Issues by Severity',
        xaxis_title='Severity',
        yaxis_title='Count'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display critical findings first
    critical_findings = [f for f in findings if f.get('severity', '') == 'critical']
    if critical_findings:
        st.subheader("⚠️ Critical Issues")
        
        for finding in critical_findings:
            component = finding.get('component', '')
            issue = finding.get('issue', '')
            evidence = finding.get('evidence', '')
            
            st.error(f"**{component}**: {issue}")
            st.text(evidence)
