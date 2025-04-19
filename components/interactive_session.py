import streamlit as st
import time
import os
import json
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def init_interactive_session():
    """Initialize interactive session state variables."""
    if 'interactive_mode' not in st.session_state:
        st.session_state.interactive_mode = False
    
    if 'analysis_stage' not in st.session_state:
        st.session_state.analysis_stage = 'initial'
        
    if 'analysis_history' not in st.session_state:
        st.session_state.analysis_history = []
        
    if 'current_hypothesis' not in st.session_state:
        st.session_state.current_hypothesis = None
        
    if 'diagnostic_path' not in st.session_state:
        st.session_state.diagnostic_path = []
        
    if 'selected_component' not in st.session_state:
        st.session_state.selected_component = None
        
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = 'welcome'
        
    # Ensure logs directory exists
    try:
        if not os.path.exists("logs"):
            os.makedirs("logs")
            logger.info("Created logs directory")
            
        # Test write access
        test_file = os.path.join("logs", "session_init_test.txt")
        with open(test_file, "w") as f:
            f.write("Session initialized")
        os.remove(test_file)
        logger.info("Verified write access to logs directory")
    except Exception as e:
        logger.error(f"Error setting up logs directory: {str(e)}")
        st.error(f"Error setting up logs directory: {str(e)}")
        
    # Initialize connection recovery features
    if 'connection_retry_count' not in st.session_state:
        st.session_state.connection_retry_count = 0

def start_interactive_session(initial_findings: List[Dict]):
    """
    Start a new interactive diagnostic session.
    
    Args:
        initial_findings: Initial findings to begin the session with
    """
    st.session_state.interactive_mode = True
    st.session_state.analysis_stage = 'component_selection'
    st.session_state.analysis_history = [{'stage': 'initial', 'findings': initial_findings, 'timestamp': time.time()}]
    st.session_state.diagnostic_path = []
    st.session_state.selected_component = None
    st.session_state.current_hypothesis = None

def end_interactive_session():
    """End the interactive diagnostic session."""
    st.session_state.interactive_mode = False
    
def add_to_history(stage: str, data: Dict):
    """
    Add an entry to the analysis history.
    
    Args:
        stage: Current analysis stage
        data: Data for this stage
    """
    if 'analysis_history' in st.session_state:
        st.session_state.analysis_history.append({
            'stage': stage,
            'data': data,
            'timestamp': time.time()
        })

def render_interactive_session(coordinator):
    """
    Render the interactive diagnostic session UI.
    
    Args:
        coordinator: The MCP coordinator instance
    """
    if not st.session_state.interactive_mode:
        return
    
    st.markdown("---")
    st.header("🔍 Interactive Root Cause Analysis")
    
    # Render the appropriate UI based on the current stage
    current_stage = st.session_state.analysis_stage
    
    if current_stage == 'component_selection':
        _render_component_selection(coordinator)
    elif current_stage == 'hypothesis_generation':
        _render_hypothesis_generation(coordinator)
    elif current_stage == 'investigation':
        _render_investigation(coordinator)
    elif current_stage == 'conclusion':
        _render_conclusion(coordinator)
    
    # Always show the diagnostic path
    _render_diagnostic_path()
    
    # Option to restart or end the session
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⏮️ Restart Analysis"):
            # Keep interactive mode on but reset the session
            st.session_state.analysis_stage = 'component_selection'
            st.session_state.diagnostic_path = []
            st.session_state.selected_component = None
            st.session_state.current_hypothesis = None
            st.rerun()
    
    with col2:
        if st.button("❌ End Interactive Session"):
            end_interactive_session()
            st.rerun()

def _render_component_selection(coordinator):
    """
    Render the component selection stage.
    
    Args:
        coordinator: The MCP coordinator instance
    """
    st.subheader("Step 1: Select a Component to Investigate")
    
    # Get the initial findings if available
    if not st.session_state.analysis_history:
        st.warning("No initial findings available. Please run an analysis first.")
        return
    
    initial_analysis = st.session_state.analysis_history[0]
    findings = initial_analysis.get('findings', [])
    
    if not findings:
        st.info("No issues found to investigate.")
        return
    
    # Group findings by component type
    component_groups = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
            
        component = finding.get('component', 'Unknown')
        component_type = component.split('/')[0] if '/' in component else 'Other'
        
        if component_type not in component_groups:
            component_groups[component_type] = []
            
        component_groups[component_type].append(finding)
    
    # Create expandable sections for each component type
    for component_type, group_findings in component_groups.items():
        with st.expander(f"{component_type}s ({len(group_findings)})", expanded=True):
            # Display each finding in the group
            for finding in group_findings:
                component = finding.get('component', 'Unknown')
                issue = finding.get('issue', 'Unknown issue')
                severity = finding.get('severity', 'info')
                
                # Color-code severity
                if severity == 'critical':
                    severity_color = "red"
                elif severity == 'high':
                    severity_color = "#FF6B6B"
                elif severity == 'medium':
                    severity_color = "#FFAC4B"
                elif severity == 'low':
                    severity_color = "#4B93FF"
                else:
                    severity_color = "#6BCB77"
                
                # Create a clickable button for each finding
                button_label = f"{component}: {issue}"
                # Create a unique key using the index in the loop along with component and issue
                unique_index = id(finding)  # Use the memory address as a unique identifier
                if st.button(button_label, key=f"btn_{component}_{unique_index}"):
                    st.session_state.selected_component = component
                    st.session_state.analysis_stage = 'hypothesis_generation'
                    
                    # Generate hypotheses for this component
                    hypotheses = coordinator.generate_hypotheses(component, finding)
                    
                    # Store the hypotheses and the finding
                    add_to_history('component_selection', {
                        'component': component,
                        'finding': finding,
                        'hypotheses': hypotheses
                    })
                    
                    st.rerun()
                
                # Display severity below the button
                st.markdown(f"<span style='color:{severity_color}'>Severity: {severity.capitalize()}</span>", unsafe_allow_html=True)
                st.markdown("---")

def _render_hypothesis_generation(coordinator):
    """
    Render the hypothesis generation stage.
    
    Args:
        coordinator: The MCP coordinator instance
    """
    st.subheader("Step 2: Select a Hypothesis to Test")
    
    # Get the latest history entry
    if len(st.session_state.analysis_history) < 2:
        st.warning("No hypothesis data available. Please select a component first.")
        return
    
    # Find the latest component selection or hypothesis rejection entry
    component_entry_idx = -1
    latest_rejection_idx = -1
    
    for i in range(len(st.session_state.analysis_history) - 1, -1, -1):
        entry = st.session_state.analysis_history[i]
        entry_stage = entry.get('stage')
        
        if entry_stage == 'component_selection' and component_entry_idx == -1:
            component_entry_idx = i
        
        if entry_stage == 'hypothesis_rejection' and latest_rejection_idx == -1:
            latest_rejection_idx = i
    
    # Prioritize the most recent hypothesis rejection if available
    if latest_rejection_idx != -1:
        hypothesis_data = st.session_state.analysis_history[latest_rejection_idx].get('data', {})
    elif component_entry_idx != -1:
        hypothesis_data = st.session_state.analysis_history[component_entry_idx].get('data', {})
    else:
        st.warning("Could not find component selection data. Please select a component first.")
        return
    component = hypothesis_data.get('component', 'Unknown')
    finding = hypothesis_data.get('finding', {})
    hypotheses = hypothesis_data.get('hypotheses', [])
    
    st.markdown(f"**Selected Component:** {component}")
    st.markdown(f"**Issue:** {finding.get('issue', 'Unknown issue')}")
    
    if not hypotheses:
        st.info("No hypotheses generated. Please go back and select another component.")
        return
    
    st.markdown("### Potential Root Causes")
    st.markdown("Select a hypothesis to investigate:")
    
    # Display each hypothesis as a selectable option
    for i, hypothesis in enumerate(hypotheses, 1):
        hypothesis_desc = hypothesis.get('description', f"Hypothesis {i}")
        confidence = hypothesis.get('confidence', 0.5)
        investigation_steps = hypothesis.get('investigation_steps', [])
        
        # Create expandable section for each hypothesis
        with st.expander(f"{i}. {hypothesis_desc}", expanded=i==1):
            st.markdown(f"**Confidence:** {confidence*100:.0f}%")
            
            if investigation_steps:
                st.markdown("**Investigation Steps:**")
                for j, step in enumerate(investigation_steps, 1):
                    st.markdown(f"{j}. {step}")
            # Show evidence for this hypothesis if available
            st.markdown("#### Evidence")
            # Get any gathered evidence for this hypothesis
            evidence_files = []
            try:
                # Safely handle directory listing
                if os.path.exists("logs"):
                    for file in os.listdir("logs"):
                        if file.endswith(".json"):
                            try:
                                with open(os.path.join("logs", file), "r") as f:
                                    log_data = json.load(f)
                                    # Check if this is related to our hypothesis
                                    log_component = log_data.get("component")
                                    log_hypothesis = log_data.get("hypothesis", {})
                                    if (log_component == component and 
                                        log_hypothesis.get("description") == hypothesis_desc):
                                        evidence_files.append((file, log_data))
                            except Exception as e:
                                logger.error(f"Error reading log file {file}: {str(e)}")
                else:
                    logger.warning("Logs directory does not exist")
                    st.info("No evidence logs found. The logs directory does not exist.")
            except Exception as e:
                logger.error(f"Error accessing logs directory: {str(e)}")
                st.error(f"Error accessing evidence logs: {str(e)}")
            
            if evidence_files:
                st.markdown("### Evidence for this hypothesis")
                for file_name, log_data in evidence_files:
                    st.markdown(f"**Log file:** {file_name}")
                    
                    # Show evidence from the log
                    evidence = log_data.get("evidence", {})
                    for evidence_type, evidence_data in evidence.items():
                        if evidence_type.endswith("_error"):
                            # This is an error message
                            st.error(f"**{evidence_type}:** {evidence_data}")
                        elif evidence_type == "pod_logs" or evidence_type == "sample_pod_logs":
                            # Show logs in a text area
                            st.markdown(f"**{evidence_type.replace('_', ' ').title()}**")
                            st.text_area(f"{evidence_type}", evidence_data, height=200, key=f"{evidence_type}_{file_name}")
                        elif evidence_type.endswith("_events"):
                            # Show events
                            st.markdown(f"**{evidence_type.replace('_', ' ').title()}**")
                            try:
                                # Try to parse events if they're in JSON format
                                if isinstance(evidence_data, list):
                                    for i, event in enumerate(evidence_data[:5]):  # Show first 5 events
                                        reason = event.get("reason", "Unknown")
                                        message = event.get("message", "No message")
                                        st.markdown(f"Event {i+1}: **{reason}** - {message}")
                                else:
                                    st.text_area(f"{evidence_type}", str(evidence_data), height=150, key=f"{evidence_type}_{file_name}")
                            except:
                                st.text_area(f"{evidence_type}", str(evidence_data), height=150, key=f"{evidence_type}_{file_name}")
                        else:
                            # Default display for other evidence types
                            st.markdown(f"**{evidence_type.replace('_', ' ').title()}**")
                            try:
                                if isinstance(evidence_data, dict) or isinstance(evidence_data, list):
                                    st.json(evidence_data)
                                else:
                                    st.text_area(f"{evidence_type}", str(evidence_data), height=100, key=f"{evidence_type}_{file_name}")
                            except:
                                st.text_area(f"{evidence_type}", str(evidence_data), height=100, key=f"{evidence_type}_{file_name}")
            else:
                st.info("No evidence files found for this hypothesis. Evidence will be gathered during investigation.")
            
            # Button to select this hypothesis
            # Create a unique key using a combination of component, index, and hypothesis description hash
            unique_key = f"hyp_{component}_{i}_{hash(hypothesis_desc) % 10000}"
            if st.button(f"Investigate this hypothesis", key=unique_key):
                st.session_state.current_hypothesis = hypothesis
                st.session_state.analysis_stage = 'investigation'
                
                # Add to diagnostic path
                st.session_state.diagnostic_path.append({
                    'type': 'hypothesis',
                    'description': hypothesis_desc,
                    'confidence': confidence
                })
                
                # Get investigation plan
                investigation_plan = coordinator.get_investigation_plan(
                    component, 
                    finding, 
                    hypothesis
                )
                
                # Store the investigation plan
                add_to_history('hypothesis_selection', {
                    'component': component,
                    'finding': finding,
                    'hypothesis': hypothesis,
                    'investigation_plan': investigation_plan
                })
                
                st.rerun()

def _render_investigation(coordinator):
    """
    Render the investigation stage.
    
    Args:
        coordinator: The MCP coordinator instance
    """
    st.subheader("Step 3: Investigation")
    
    # Get the latest history entry
    if len(st.session_state.analysis_history) < 3:
        st.warning("No investigation data available. Please select a hypothesis first.")
        return
    
    investigation_data = st.session_state.analysis_history[-1].get('data', {})
    component = investigation_data.get('component', 'Unknown')
    finding = investigation_data.get('finding', {})
    hypothesis = investigation_data.get('hypothesis', {})
    investigation_plan = investigation_data.get('investigation_plan', {})
    
    st.markdown(f"**Selected Component:** {component}")
    st.markdown(f"**Issue:** {finding.get('issue', 'Unknown issue')}")
    st.markdown(f"**Testing Hypothesis:** {hypothesis.get('description', 'Unknown hypothesis')}")
    
    # Display investigation steps
    investigation_steps = investigation_plan.get('steps', [])
    evidence = investigation_plan.get('evidence', {})
    conclusion = investigation_plan.get('conclusion', {})
    next_steps = investigation_plan.get('next_steps', [])
    
    if investigation_steps:
        st.markdown("### Investigation Steps")
        
        for i, step in enumerate(investigation_steps, 1):
            step_desc = step.get('description', f"Step {i}")
            step_result = step.get('result', "Pending")
            
            st.markdown(f"**{i}. {step_desc}**")
            st.markdown(f"Result: {step_result}")
            st.markdown("---")
    
    # Display evidence
    if evidence:
        st.markdown("### Evidence Collected")
        
        for evidence_type, evidence_data in evidence.items():
            st.markdown(f"**{evidence_type.capitalize()}:**")
            st.text(evidence_data)
    
    # Display conclusion
    if conclusion:
        st.markdown("### Conclusion")
        
        conclusion_text = conclusion.get('text', "No conclusion reached.")
        confidence = conclusion.get('confidence', 0.0)
        
        st.markdown(f"**Assessment:** {conclusion_text}")
        st.markdown(f"**Confidence:** {confidence*100:.0f}%")
        
        # Option to accept conclusion
        conclusion_key = f"accept_conclusion_{component}_{hash(conclusion_text) % 10000}"
        if st.button("Accept this conclusion", key=conclusion_key):
            st.session_state.analysis_stage = 'conclusion'
            
            # Add to diagnostic path
            st.session_state.diagnostic_path.append({
                'type': 'conclusion',
                'description': conclusion_text,
                'confidence': confidence
            })
            
            # Store the conclusion
            conclusion_data = {
                'component': component,
                'finding': finding,
                'hypothesis': hypothesis,
                'conclusion': conclusion,
                'confirmed': True
            }
            
            # Log the conclusion with evidence
            try:
                if 'coordinator' in locals() and hasattr(coordinator, 'evidence_logger'):
                    # Find all evidence files related to this hypothesis
                    evidence_files = []
                    if hasattr(coordinator, 'evidence_logger'):
                        evidence_files = [e.get('evidence_log', '') for e in 
                                         coordinator.evidence_logger.get_evidence_for_hypothesis(
                                             component, hypothesis.get('description', ''))]
                        
                    # Log the conclusion
                    log_path = coordinator.evidence_logger.log_conclusion(
                        component=component,
                        hypothesis=hypothesis,
                        conclusion=conclusion,
                        evidence_paths=evidence_files
                    )
                    conclusion_data['evidence_log'] = log_path
            except Exception as e:
                st.error(f"Error logging conclusion: {str(e)}")
            
            add_to_history('conclusion', conclusion_data)
            
            st.rerun()
    
    # Display next steps
    if next_steps:
        st.markdown("### Next Steps to Investigate")
        
        for i, step in enumerate(next_steps, 1):
            step_desc = step.get('description', f"Next step {i}")
            step_type = step.get('type', 'unknown')
            
            # Button to select this next step
            # Create a unique key combining component name, step, and step description hash
            next_step_key = f"next_{component}_{i}_{hash(step_desc) % 10000}"
            if st.button(f"{i}. {step_desc}", key=next_step_key):
                # Add to diagnostic path
                st.session_state.diagnostic_path.append({
                    'type': 'investigation_step',
                    'description': step_desc
                })
                
                # Execute the next step
                next_step_result = coordinator.execute_investigation_step(
                    component,
                    finding,
                    hypothesis,
                    step
                )
                
                # Store the result
                add_to_history('investigation_step', {
                    'component': component,
                    'finding': finding,
                    'hypothesis': hypothesis,
                    'step': step,
                    'result': next_step_result
                })
                
                # If the step provides a conclusion, move to conclusion stage
                if next_step_result.get('conclusion'):
                    st.session_state.analysis_stage = 'conclusion'
                    
                st.rerun()
    
    # Option to reject hypothesis and go back
    reject_key = f"reject_{component}_{hash(hypothesis.get('description', '')) % 10000}"
    if st.button("This hypothesis is incorrect, go back", key=reject_key):
        # Store the rejected hypothesis info
        rejected_hypothesis = hypothesis.get('description', 'Unknown')
        
        # Get the original component info from the component selection stage
        component_selection_idx = -1
        for i, entry in enumerate(st.session_state.analysis_history):
            if entry.get('stage') == 'component_selection':
                component_selection_idx = i
                break
        
        if component_selection_idx >= 0:
            # Get the component data
            component_data = st.session_state.analysis_history[component_selection_idx].get('data', {})
            component = component_data.get('component')
            finding = component_data.get('finding', {})
            hypotheses = component_data.get('hypotheses', [])
            
            # Remove this hypothesis from the list if it exists
            new_hypotheses = [h for h in hypotheses if h.get('description') != hypothesis.get('description')]
            
            # If we still have hypotheses, go back to hypothesis generation
            if new_hypotheses:
                # Add entry to history first
                add_to_history('hypothesis_rejection', {
                    'component': component,
                    'finding': finding,
                    'rejected_hypothesis': hypothesis,
                    'hypotheses': new_hypotheses,
                    'message': f"Rejected hypothesis: {rejected_hypothesis}"
                })
                
                # Then change the stage
                st.session_state.analysis_stage = 'hypothesis_generation'
                
                # Add to diagnostic path
                st.session_state.diagnostic_path.append({
                    'type': 'rejection',
                    'description': f"Rejected: {rejected_hypothesis}"
                })
            else:
                # If no more hypotheses, go back to component selection
                st.session_state.analysis_stage = 'component_selection'
                
                # Add entry to history
                add_to_history('return_to_components', {
                    'message': f"All hypotheses rejected for {component}"
                })
                
                # Add to diagnostic path
                st.session_state.diagnostic_path.append({
                    'type': 'rejection',
                    'description': f"All hypotheses rejected for {component}"
                })
        else:
            # Fallback if we can't find the component
            st.session_state.analysis_stage = 'component_selection'
        
        st.rerun()

def _render_conclusion(coordinator):
    """
    Render the conclusion stage.
    
    Args:
        coordinator: The MCP coordinator instance
    """
    st.subheader("Root Cause Identified")
    
    # Get the conclusion data
    conclusion_data = st.session_state.analysis_history[-1].get('data', {})
    component = conclusion_data.get('component', 'Unknown')
    finding = conclusion_data.get('finding', {})
    hypothesis = conclusion_data.get('hypothesis', {})
    conclusion = conclusion_data.get('conclusion', {})
    
    st.markdown(f"**Component:** {component}")
    st.markdown(f"**Issue:** {finding.get('issue', 'Unknown issue')}")
    
    # Display the conclusion
    st.markdown("### Root Cause Analysis")
    
    conclusion_text = conclusion.get('text', "No conclusion reached.")
    confidence = conclusion.get('confidence', 0.0)
    recommendations = conclusion.get('recommendations', [])
    
    st.markdown(f"**Root Cause:** {conclusion_text}")
    st.markdown(f"**Confidence:** {confidence*100:.0f}%")
    
    # Display recommendations
    if recommendations:
        st.markdown("### Recommendations")
        
        for i, recommendation in enumerate(recommendations, 1):
            st.markdown(f"{i}. {recommendation}")
    
    # Option to investigate another component
    if st.button("Investigate another component", key=f"investigate_another_{component}"):
        st.session_state.analysis_stage = 'component_selection'
        st.rerun()
    
    # Option to get a full report
    if st.button("Generate Full Analysis Report", key=f"generate_report_{component}"):
        report = coordinator.generate_root_cause_report(st.session_state.analysis_history)
        
        # Store the report
        add_to_history('report', {
            'report': report
        })
        
        # Display the report
        st.markdown("### Full Analysis Report")
        st.markdown(report)

def _render_diagnostic_path():
    """Render the diagnostic path taken so far."""
    if not st.session_state.diagnostic_path:
        return
    
    st.markdown("### Diagnostic Path")
    
    # Create a horizontal timeline
    path = st.session_state.diagnostic_path
    steps_html = ""
    
    for i, step in enumerate(path):
        step_type = step.get('type', 'unknown')
        description = step.get('description', f"Step {i+1}")
        
        # Choose icon and color based on step type
        if step_type == 'hypothesis':
            icon = "🔍"
            color = "#4B93FF"
        elif step_type == 'investigation_step':
            icon = "⚙️"
            color = "#FFAC4B"
        elif step_type == 'conclusion':
            icon = "✅"
            color = "#6BCB77"
        elif step_type == 'rejection':
            icon = "❌"
            color = "#FF6B6B"
        else:
            icon = "🔄"
            color = "#B8B8B8"
        
        # Create step HTML
        steps_html += f"""
        <div style="display: inline-block; text-align: center; margin: 0 5px;">
            <div style="font-size: 24px;">{icon}</div>
            <div style="width: 80px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; color: {color};">
                {description[:20]}{"..." if len(description) > 20 else ""}
            </div>
        </div>
        """
        
        # Add arrow unless it's the last step
        if i < len(path) - 1:
            steps_html += """
            <div style="display: inline-block; margin: 0 5px;">
                <div style="font-size: 24px;">➡️</div>
                <div style="width: 20px;"></div>
            </div>
            """
    
    # Create the timeline container
    timeline_html = f"""
    <div style="overflow-x: auto; white-space: nowrap; padding: 10px 0;">
        {steps_html}
    </div>
    """
    
    st.markdown(timeline_html, unsafe_allow_html=True)