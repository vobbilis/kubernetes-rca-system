import streamlit as st
import pandas as pd

def render_report(analysis_results, analysis_type):
    """
    Render a detailed report of the analysis results.
    
    Args:
        analysis_results: Results from the analysis
        analysis_type: Type of analysis that was performed
    """
    st.header("📋 Detailed Analysis Report")
    
    if 'error' in analysis_results:
        st.error(f"Error during analysis: {analysis_results['error']}")
        return
    
    # Show metadata
    metadata = analysis_results.get('metadata', {})
    if metadata:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Analysis Type", metadata.get('analysis_type', 'Unknown'))
        with col2:
            st.metric("Namespace", metadata.get('namespace', 'Unknown'))
        with col3:
            st.metric("Context", metadata.get('context', 'Unknown'))
    
    # Create tabs for the report sections
    if analysis_type == 'comprehensive':
        _render_comprehensive_report(analysis_results)
    elif analysis_type == 'resources':
        # For resource analysis, show resource status summaries and findings
        resource_count = analysis_results.get('resource_count', {})
        findings = analysis_results.get('findings', [])
        reasoning_steps = analysis_results.get('reasoning_steps', [])
        
        # Show resource counts
        if resource_count:
            st.subheader("Resource Summary")
            cols = st.columns(len(resource_count))
            
            for i, (resource_type, count) in enumerate(resource_count.items()):
                with cols[i]:
                    st.metric(f"{resource_type.capitalize()}", count)
        
        _render_findings_section(findings)
        _render_reasoning_section(reasoning_steps)
    else:
        # For other single agent analysis, show findings and reasoning steps
        findings = analysis_results.get('findings', [])
        reasoning_steps = analysis_results.get('reasoning_steps', [])
        
        _render_findings_section(findings)
        _render_reasoning_section(reasoning_steps)

def _render_comprehensive_report(results):
    """
    Render a report for comprehensive analysis results.
    
    Args:
        results: Comprehensive analysis results
    """
    # Create tabs for the different report sections
    tabs = st.tabs(["Root Causes", "Correlated Issues", "Resources", "Metrics", "Logs", "Topology", "Events", "Traces"])
    
    # Root Causes tab
    with tabs[0]:
        root_causes = results.get('root_causes', [])
        if root_causes:
            st.subheader("Identified Root Causes")
            
            for i, root_cause in enumerate(root_causes, 1):
                if isinstance(root_cause, dict):
                    component = root_cause.get('component', 'Unknown')
                    severity = root_cause.get('severity', 'Unknown')
                    explanation = root_cause.get('explanation', '')
                    related_count = root_cause.get('related_findings_count', 0)
                    
                    st.markdown(f"### {i}. {component}")
                    st.markdown(f"**Severity:** {severity.capitalize()}")
                    st.markdown(f"**Related Findings:** {related_count}")
                    st.markdown(f"**Explanation:** {explanation}")
                else:
                    # If root_cause is a string, just display it
                    st.markdown(f"### {i}. Root Cause")
                    st.markdown(root_cause)
                
                st.markdown("---")
        else:
            st.info("No root causes identified in the analysis.")
    
    # Correlated Issues tab
    with tabs[1]:
        correlated_findings = results.get('correlated_findings', [])
        if correlated_findings:
            st.subheader("Issues with Correlations")
            
            for i, finding in enumerate(correlated_findings, 1):
                # Check if finding is a dictionary or string
                if isinstance(finding, dict):
                    component = finding.get('component', 'Unknown')
                    related_findings = finding.get('related_findings', [])
                    correlation_type = finding.get('correlation_type', 'Unknown')
                    severity = finding.get('severity', 'info')
                    
                    st.markdown(f"### {i}. {component}")
                    st.markdown(f"**Correlation Type:** {correlation_type}")
                    st.markdown(f"**Severity:** {severity.capitalize()}")
                    st.markdown(f"**Related Issues:** {len(related_findings)}")
                    
                    # Show the related findings
                    if related_findings:
                        for j, related in enumerate(related_findings, 1):
                            if isinstance(related, dict):
                                issue = related.get('issue', 'Unknown issue')
                                severity = related.get('severity', 'info')
                                st.markdown(f"- **{severity.capitalize()}:** {issue}")
                            else:
                                st.markdown(f"- {related}")
                else:
                    # If finding is a string, just display it
                    st.markdown(f"### {i}. Finding")
                    st.markdown(finding)
                
                st.markdown("---")
        else:
            st.info("No correlated issues identified in the analysis.")
    
    # Resources tab
    with tabs[2]:
        resources_results = results.get('resources', {})
        if resources_results:
            # Display resource counts if available
            resource_count = resources_results.get('resource_count', {})
            if resource_count:
                st.subheader("Resource Summary")
                cols = st.columns(len(resource_count))
                
                for i, (resource_type, count) in enumerate(resource_count.items()):
                    with cols[i]:
                        st.metric(f"{resource_type.capitalize()}", count)
            
            # Display findings
            findings = resources_results.get('findings', [])
            reasoning_steps = resources_results.get('reasoning_steps', [])
            
            _render_findings_section(findings)
            _render_reasoning_section(reasoning_steps)
        else:
            st.info("No resource analysis results available.")
    
    # Metrics tab
    with tabs[3]:
        metrics_results = results.get('metrics', {})
        _render_agent_results(metrics_results, "Metrics Analysis")
    
    # Logs tab
    with tabs[4]:
        logs_results = results.get('logs', {})
        _render_agent_results(logs_results, "Logs Analysis")
    
    # Topology tab
    with tabs[5]:
        topology_results = results.get('topology', {})
        _render_agent_results(topology_results, "Topology Analysis")
    
    # Events tab
    with tabs[6]:
        events_results = results.get('events', {})
        _render_agent_results(events_results, "Events Analysis")
    
    # Traces tab
    with tabs[7]:
        traces_results = results.get('traces', {})
        _render_agent_results(traces_results, "Traces Analysis")

def _render_agent_results(agent_results, title):
    """
    Render results from a specific agent.
    
    Args:
        agent_results: Results from the agent
        title: Title for the section
    """
    if not agent_results:
        st.info(f"No {title.lower()} results available.")
        return
    
    findings = agent_results.get('findings', [])
    reasoning_steps = agent_results.get('reasoning_steps', [])
    
    _render_findings_section(findings)
    _render_reasoning_section(reasoning_steps)

def _render_findings_section(findings):
    """
    Render a section for findings.
    
    Args:
        findings: List of findings
    """
    if not findings:
        st.info("No findings from this analysis.")
        return
    
    st.subheader("Findings")
    
    # Filter to only use dict findings for sorting
    dict_findings = [f for f in findings if isinstance(f, dict)]
    string_findings = [f for f in findings if isinstance(f, str)]
    
    if dict_findings:
        # Sort findings by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
        sorted_findings = sorted(dict_findings, key=lambda f: severity_order.get(f.get('severity', 'info'), 999))
        
        # Display an expandable section for each finding
        for i, finding in enumerate(sorted_findings, 1):
            component = finding.get('component', 'Unknown')
            issue = finding.get('issue', 'Unknown issue')
            severity = finding.get('severity', 'info')
            evidence = finding.get('evidence', '')
            recommendation = finding.get('recommendation', '')
            
            # Choose color based on severity
            if severity == 'critical':
                title_html = f"<span style='color:red'>CRITICAL</span>: {component} - {issue}"
            elif severity == 'high':
                title_html = f"<span style='color:#FF6B6B'>HIGH</span>: {component} - {issue}"
            elif severity == 'medium':
                title_html = f"<span style='color:#FFAC4B'>MEDIUM</span>: {component} - {issue}"
            elif severity == 'low':
                title_html = f"<span style='color:#4B93FF'>LOW</span>: {component} - {issue}"
            else:
                title_html = f"<span style='color:#6BCB77'>INFO</span>: {component} - {issue}"
            
            with st.expander(f"{i}. {component} - {issue}"):
                st.markdown(f"**Severity:** {severity.capitalize()}")
                
                if evidence:
                    st.markdown("**Evidence:**")
                    st.text(evidence)
                
                if recommendation:
                    st.markdown("**Recommendation:**")
                    st.info(recommendation)
    
    # Display string findings
    for i, finding in enumerate(string_findings, len(dict_findings) + 1):
        with st.expander(f"{i}. Finding"):
            st.markdown(finding)

def _render_reasoning_section(reasoning_steps):
    """
    Render a section for reasoning steps.
    
    Args:
        reasoning_steps: List of reasoning steps
    """
    if not reasoning_steps:
        return
    
    with st.expander("Agent Reasoning Process", expanded=False):
        st.subheader("Reasoning Steps")
        
        for i, step in enumerate(reasoning_steps, 1):
            if isinstance(step, dict):
                observation = step.get('observation', '')
                conclusion = step.get('conclusion', '')
                
                st.markdown(f"### Step {i}")
                st.markdown(f"**Observation:** {observation}")
                st.markdown(f"**Conclusion:** {conclusion}")
            else:
                # If step is a string, just display it
                st.markdown(f"### Step {i}")
                st.markdown(step)
            
            st.markdown("---")
