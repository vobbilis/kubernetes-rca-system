import streamlit as st
import time
import json
from typing import Dict, List, Any, Optional

def init_chatbot_interface():
    """Initialize the chatbot interface state variables."""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    if 'current_suggestions' not in st.session_state:
        st.session_state.current_suggestions = []
    
    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""
        
    if 'accumulated_findings' not in st.session_state:
        st.session_state.accumulated_findings = []

def add_message(role: str, content: str, investigation_id: Optional[str] = None, db_handler = None):
    """
    Add a message to the chat history.
    
    Args:
        role: The role of the message sender ('user', 'assistant', or 'system')
        content: The message content
        investigation_id: Optional investigation ID to persist the message
        db_handler: Optional database handler to persist the message
    """
    # Add to session state
    st.session_state.chat_history.append({
        'role': role,
        'content': content,
        'timestamp': time.time()
    })
    
    # Persist to database if provided
    if investigation_id and db_handler:
        db_handler.add_conversation_entry(
            investigation_id=investigation_id,
            role=role,
            content=content
        )

def add_suggestions(suggestions: List[Dict[str, Any]], investigation_id: Optional[str] = None, db_handler = None):
    """
    Add suggested next actions to the chatbot interface.
    
    Args:
        suggestions: List of suggestion objects with 'text' and 'action' keys
        investigation_id: Optional investigation ID to persist the suggestions
        db_handler: Optional database handler to persist the suggestions
    """
    st.session_state.current_suggestions = suggestions
    
    # Persist to database if provided
    if investigation_id and db_handler:
        db_handler.update_next_actions(
            investigation_id=investigation_id,
            next_actions=suggestions
        )

def load_chat_history(investigation_id: str, db_handler):
    """
    Load chat history from the database.
    
    Args:
        investigation_id: Investigation ID to load history from
        db_handler: Database handler to load the history
    """
    investigation = db_handler.get_investigation(investigation_id)
    if not investigation:
        return
    
    # Load conversation history
    if 'conversation' in investigation:
        st.session_state.chat_history = investigation['conversation']
    
    # Load suggested next actions
    if 'next_actions' in investigation:
        st.session_state.current_suggestions = investigation['next_actions']
        
    # Load accumulated findings if available
    if 'accumulated_findings' in investigation:
        st.session_state.accumulated_findings = investigation['accumulated_findings']
    else:
        # Initialize with empty list if not present
        st.session_state.accumulated_findings = []

def get_initial_suggestions():
    """
    Returns a list of initial suggestions to show when a new investigation is started.
    
    Returns:
        List of suggestion objects with text and action keys
    """
    return [
        {
            "text": "Check the health of my cluster",
            "action": {
                "type": "query",
                "query": "Check the overall health of my Kubernetes cluster and show me any issues"
            }
        },
        {
            "text": "What services are running in my cluster?",
            "action": {
                "type": "query",
                "query": "List all services running in my Kubernetes cluster and their status"
            }
        },
        {
            "text": "Are any of my applications slow?",
            "action": {
                "type": "query",
                "query": "Identify any applications or services that have performance issues or high latency"
            }
        },
        {
            "text": "Show failed pods",
            "action": {
                "type": "query",
                "query": "List all failed or problematic pods and explain why they're failing"
            }
        },
        {
            "text": "Analyze resource usage",
            "action": {
                "type": "run_agent",
                "agent_type": "resources"
            }
        }
    ]

def render_chatbot_interface(
    coordinator,
    k8s_client,
    investigation_id: Optional[str] = None,
    db_handler = None
):
    """
    Render the chatbot interface.
    
    Args:
        coordinator: The MCP coordinator instance
        k8s_client: Kubernetes client instance
        investigation_id: Optional investigation ID for persistence
        db_handler: Optional database handler for persistence
    """
    print(f"DEBUG [chatbot_interface.py]: Rendering chatbot interface with investigation_id: {investigation_id}")
    
    # Critical check: If investigation_id is None, create one
    if not investigation_id:
        print(f"WARNING [chatbot_interface.py]: No investigation_id provided! Creating a new one.")
        try:
            if db_handler:
                # Create a temporary investigation automatically
                investigation_id = db_handler.create_investigation(
                    title=f"Auto-created Investigation ({time.strftime('%Y-%m-%d %H:%M')})",
                    namespace="default",
                    context=""
                )
                
                # Set all session state variables
                st.session_state['current_investigation_id'] = investigation_id
                st.session_state['selected_investigation'] = investigation_id
                st.session_state['active_investigation'] = investigation_id
                st.session_state['chat_target_id'] = investigation_id
                st.session_state['view_mode'] = 'chat'
                
                # Add system message
                db_handler.add_conversation_entry(
                    investigation_id=investigation_id,
                    role="system",
                    content=f"Auto-created investigation at {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                st.info(f"Created new investigation automatically with ID: {investigation_id}")
                print(f"DEBUG [chatbot_interface.py]: Created new investigation with ID: {investigation_id}")
            else:
                # No DB handler provided, use in-memory only
                st.warning("No database handler available. Chat history will not be persisted.")
                print(f"ERROR [chatbot_interface.py]: No db_handler provided, cannot create investigation")
        except Exception as e:
            st.error(f"Error creating investigation: {str(e)}")
            print(f"ERROR [chatbot_interface.py]: Failed to create investigation: {str(e)}")
    
    # Page title
    st.title("Kubernetes Root Cause Analysis")
    
    # Initialize investigation
    investigation = None
    
    # Fetch investigation details if we have an ID
    if investigation_id and db_handler:
        investigation = db_handler.get_investigation(investigation_id)
        print(f"DEBUG [chatbot_interface.py]: Got investigation from db_handler: {investigation is not None}")
    
    # Load chat history if this is a continuing investigation
    if investigation_id and db_handler:
        if not st.session_state.chat_history:
            print(f"DEBUG [chatbot_interface.py]: Loading chat history for investigation {investigation_id}")
            load_chat_history(investigation_id, db_handler)
            
            # If this is a new chat with no history, add initial suggestions
            if not st.session_state.chat_history or len(st.session_state.chat_history) <= 1:  # 1 for just the system message
                print(f"DEBUG [chatbot_interface.py]: Adding initial suggestions for new investigation")
                initial_suggestions = get_initial_suggestions()
                add_suggestions(initial_suggestions, investigation_id, db_handler)
        else:
            print(f"DEBUG [chatbot_interface.py]: Chat history already loaded, length: {len(st.session_state.chat_history)}")
    
    # Custom CSS for a single unified canvas with sections
    st.markdown("""
    <style>
    .chat-unified-canvas {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 15px;
        background-color: #fafafa;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        display: flex;
        flex-direction: column;
        max-height: calc(100vh - 200px);
    }
    
    .chat-header {
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #eee;
    }
    
    .chat-messages-area {
        flex: 1;
        overflow-y: auto;
        padding: 10px;
        background-color: white;
        border-radius: 5px;
        border: 1px solid #eee;
        margin-bottom: 10px;
        min-height: 300px;
        max-height: calc(100vh - 400px);
    }
    
    .chat-suggestions-area {
        padding: 10px;
        background-color: #f5f5f5;
        border-radius: 5px;
        border: 1px solid #eee;
        margin-bottom: 10px;
        max-height: 150px;
        overflow-y: auto;
    }
    
    .chat-input-area {
        padding: 10px;
        background-color: white;
        border-radius: 5px;
        border: 1px solid #eee;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add global CSS for the entire chat interface with better section borders
    st.markdown("""
    <style>
    /* Apply to all chat sections */
    .chat-section {
        border: 2px solid #3f51b5;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        background-color: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        position: relative;
        width: 100%;
        box-sizing: border-box;
    }
    
    /* Override Streamlit container styles */
    div.stContainer {
        max-width: 100%;
        padding: 0;
    }
    
    /* Main container for all chat sections */
    .chat-outer-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        width: 100%;
        padding: 0;
        margin: 0;
    }
    
    /* Message area section */
    .chat-message-section {
        min-height: 350px;
        max-height: 400px;
        overflow-y: auto;
        background-color: #fcfdff;
        position: relative;
        display: flex;
        flex-direction: column;
        margin-bottom: 15px;
    }
    
    /* Suggestions section */
    .chat-suggestion-section {
        min-height: 80px;
        max-height: 150px;
        overflow-y: auto;
        background-color: #f5f7ff;
        position: relative;
        display: flex;
        flex-direction: column;
        margin-bottom: 15px;
    }
    
    /* Input section */
    .chat-input-section {
        background-color: #f9f9f9;
        position: relative;
        display: flex;
        flex-direction: column;
    }
    
    /* Fix for Streamlit containers inside our sections */
    div.chat-section > div {
        width: 100%;
        margin: 0;
        padding: 5px 10px;
    }
    
    /* Override default Streamlit element styles inside our sections */
    div.chat-section .stTextInput > div > div {
        padding: 5px;
    }
    
    /* Make buttons look better in the suggestion section */
    div.chat-suggestion-section button {
        margin: 5px;
    }
    
    /* Section headers */
    .section-header {
        font-weight: bold;
        margin-bottom: 10px;
        color: #3f51b5;
        border-bottom: 1px solid #e0e0e0;
        padding-bottom: 5px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create our main page container
    st.subheader("Conversation")

    # Use a completely native Streamlit approach with expanders that look like sections
    
    # MESSAGES SECTION - Using an expanded expander with custom styling
    with st.expander("Messages", expanded=True):
        # Add custom styling to make it look nicer
        st.markdown("""
        <style>
        /* Style for the messages expander */
        div[data-testid="stExpander"] {
            border: 2px solid #3f51b5;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 15px;
            background-color: #fcfdff;
        }
        
        /* Style for the expander header */
        div[data-testid="stExpander"] > div:first-child {
            background-color: #eef2ff;
            border-bottom: 1px solid #ddd;
            padding: 5px;
            font-weight: bold;
            color: #3f51b5;
        }
        </style>
        """, unsafe_allow_html=True)
        
        chat_output_container = st.container()
    
    # SUGGESTIONS SECTION
    with st.expander("Suggested Next Actions", expanded=True):
        suggestions_container = st.container()
    
    # INPUT SECTION
    with st.expander("Your Message", expanded=True):
        chat_input_container = st.container()
    
    # Create the chat input area in the input container
    with chat_input_container:
        # User input area at the bottom
        user_input = st.text_input("Ask about your Kubernetes cluster:", 
                                 key="user_input_field", 
                                 placeholder="e.g., What's wrong with my frontend service?")
        
        # Add buttons for send and clear
        send_col, clear_col = st.columns([5, 1])
        with send_col:
            send_button = st.button("Send", type="primary", key="send_button")
        with clear_col:
            clear_button = st.button("Clear", key="clear_button")
    
    # Handle clear button
    if clear_button:
        st.session_state.chat_history = []
        st.session_state.current_suggestions = []
        st.session_state.user_input = ""
        st.rerun()
    
    # Process user input
    if send_button and user_input:
        # Add user message to history
        add_message('user', user_input, investigation_id, db_handler)
        
        # Clear input field
        st.session_state.user_input = ""
        
        # Generate response with spinner
        with st.spinner("Analyzing..."):
            # Get the response from the coordinator, passing previous findings for context
            # Include investigation_id for proper prompt logging
            response = coordinator.process_user_query(
                query=user_input,
                namespace=st.session_state.get('selected_namespace', 'default'),
                context=st.session_state.get('selected_context', None),
                previous_findings=st.session_state.get('accumulated_findings', []),
                investigation_id=st.session_state.get('current_investigation_id')
            )
            
            # Format and add assistant response to history
            # Check if we already have structured data in response_data format
            if 'response_data' in response and isinstance(response['response_data'], dict):
                # We have structured data, use it directly
                import json
                structured_response = json.dumps(response)
                add_message('assistant', structured_response, investigation_id, db_handler)
            else:
                # We have the old format response - convert it to structured if possible
                response_text = response.get('response', "I couldn't generate a response.")
                
                # Try to convert normal text with bullet points to structured format
                lines = response_text.strip().split('\n')
                points = []
                for line in lines:
                    line = line.strip()
                    if line:
                        # Check if the line starts with a bullet marker and extract the content
                        if line.startswith('- ') or line.startswith('• '):
                            points.append(line[2:].strip())
                        else:
                            points.append(line)
                
                # Create structured response data
                if points:
                    structured_data = {
                        "response_data": {
                            "points": points
                        },
                        "response": response_text,  # Keep original for compatibility
                        "summary": response.get('summary', ""),
                        "suggestions": response.get('suggestions', [])
                    }
                    import json
                    structured_response = json.dumps(structured_data)
                    add_message('assistant', structured_response, investigation_id, db_handler)
                else:
                    # Just use the regular response if we can't structure it
                    add_message('assistant', response_text, investigation_id, db_handler)
            
            # Generate suggested next actions
            suggestions = response.get('suggestions', [])
            add_suggestions(suggestions, investigation_id, db_handler)
            
            # If there's evidence or findings, store them
            if investigation_id and db_handler:
                if 'evidence' in response:
                    for evidence_type, evidence_data in response.get('evidence', {}).items():
                        db_handler.add_evidence(
                            investigation_id=investigation_id,
                            evidence_type=evidence_type,
                            evidence_data=evidence_data
                        )
                
                if 'findings' in response:
                    db_handler.add_agent_findings(
                        investigation_id=investigation_id,
                        agent_type='coordinator',
                        findings=response.get('findings', {})
                    )
                    
            # Accumulate key findings for context in future queries
            if 'key_findings' in response and isinstance(response['key_findings'], list):
                # Add new key findings to our accumulated findings
                st.session_state.accumulated_findings.extend(response['key_findings'])
                
                # Keep the list to a reasonable size (last 20 findings)
                if len(st.session_state.accumulated_findings) > 20:
                    st.session_state.accumulated_findings = st.session_state.accumulated_findings[-20:]
                    
                # Persist findings to database if available
                if investigation_id and db_handler:
                    db_handler.update_investigation(
                        investigation_id=investigation_id,
                        updates={'accumulated_findings': st.session_state.accumulated_findings}
                    )
            
            # Generate a summary based on the first question if it's a new investigation
            # This replaces the requirement to specify the summary upfront
            if investigation_id and db_handler and 'summary' in response:
                db_handler.update_summary(
                    investigation_id=investigation_id,
                    summary=response.get('summary', '')
                )
            elif investigation_id and db_handler and len(st.session_state.chat_history) <= 2:
                # If this is the first question (chat history will have the user question + AI response)
                # and there's no summary yet, generate one from the first question
                with st.spinner("Generating investigation summary..."):
                    summary_response = coordinator.generate_summary_from_query(
                        query=user_input,
                        namespace=st.session_state.get('selected_namespace', 'default'),
                        investigation_id=investigation_id
                    )
                    if summary_response and 'summary' in summary_response:
                        db_handler.update_summary(
                            investigation_id=investigation_id,
                            summary=summary_response.get('summary', '')
                        )
        
        st.rerun()
    
    # Render the chat output (conversation history) in the top container
    with chat_output_container:
        # No need for a header here, it's already in the canvas header
        
        # Create a scrollable container for the chat messages directly within the chat messages area
        chat_container = st.container()
        
        # Add custom CSS for message styling - without container borders, 
        # as we're now using the section borders
        st.markdown("""
        <style>
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 20px;
            padding: 5px;
            max-height: 600px;
            overflow-y: auto;
            background-color: transparent;
        }
        
        .message-user {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 16px;
            animation: fadeIn 0.3s ease-in-out;
        }
        
        .message-ai {
            display: flex;
            justify-content: flex-start;
            margin-bottom: 16px;
            animation: fadeIn 0.3s ease-in-out;
        }
        
        .message-system {
            display: flex;
            justify-content: center;
            margin-bottom: 10px;
            animation: fadeIn 0.3s ease-in-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message-content-user {
            background-color: #e0e7ff;
            padding: 12px 18px;
            border-radius: 18px 18px 0 18px;
            max-width: 80%;
            text-align: right;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            color: #333;
            line-height: 1.5;
        }
        
        .message-content-ai {
            background-color: #f0f7ff;
            padding: 12px 18px;
            border-radius: 18px 18px 18px 0;
            max-width: 80%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            color: #333;
            line-height: 1.5;
        }
        
        .message-content-system {
            background-color: #ffffcc;
            padding: 8px 12px;
            border-radius: 10px;
            font-style: italic;
            font-size: 0.85em;
            max-width: 70%;
            text-align: center;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            color: #555;
        }
        
        .ai-icon {
            width: 35px;
            height: 35px;
            margin-right: 10px;
            background-color: #3f51b5; /* Material blue */
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .chat-timestamp {
            font-size: 0.7em;
            color: #777;
            margin-top: 5px;
            text-align: right;
        }
        
        .load-more-button {
            text-align: center;
            margin: 15px 0;
            padding: 5px;
            background-color: #f5f5f5;
            border-radius: 10px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        
        .load-more-button:hover {
            background-color: #e9e9e9;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if st.session_state.chat_history:
            # Determine how many messages to show
            total_messages = len(st.session_state.chat_history)
            max_visible_messages = 20
            
            # Determine if we need a "Load More" button
            start_index = max(0, total_messages - max_visible_messages)
            has_more = start_index > 0
            
            # "Load More" button if there are older messages
            if has_more:
                # We use a unique key based on start_index to ensure the button state is preserved
                if st.button("Load Older Messages", key=f"load_more_{start_index}"):
                    # Show 20 more messages
                    start_index = max(0, start_index - 20)
            
            # HTML for the beginning of the chat container
            chat_html = '<div class="chat-container">'
            
            # Create HTML for all messages in the visible range
            visible_messages = st.session_state.chat_history[start_index:total_messages]
            
            for message in visible_messages:
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                timestamp = message.get('timestamp', 0)
                
                # Format timestamp - handle both string and numeric timestamps
                formatted_time = ""
                if timestamp:
                    try:
                        # If timestamp is a number (unix timestamp)
                        if isinstance(timestamp, (int, float)):
                            formatted_time = time.strftime('%H:%M:%S', time.localtime(timestamp))
                        # If timestamp is already a formatted string
                        elif isinstance(timestamp, str):
                            formatted_time = timestamp
                    except Exception as e:
                        print(f"Error formatting timestamp: {e}")
                
                # Process the content for HTML display (convert newlines to <br>, escape HTML)
                # First, replace any specific HTML tags with their escaped versions
                processed_content = content.replace('<', '&lt;').replace('>', '&gt;')
                # Then convert newlines to <br> tags for proper HTML line breaks
                processed_content = processed_content.replace('\n', '<br>')
                
                if role == 'user':
                    chat_html += f"""
                    <div class="message-user">
                        <div class="message-content-user">
                            {processed_content}
                            <div class="chat-timestamp">{formatted_time}</div>
                        </div>
                    </div>
                    """
                elif role == 'assistant':
                    chat_html += f"""
                    <div class="message-ai">
                        <div class="ai-icon" style="width: 35px; height: 35px; margin-right: 10px; background-color: #3f51b5; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 14px;">AI</div>
                        <div class="message-content-ai">
                            {processed_content}
                            <div class="chat-timestamp">{formatted_time}</div>
                        </div>
                    </div>
                    """
                elif role == 'system':
                    chat_html += f"""
                    <div class="message-system">
                        <div class="message-content-system">
                            {processed_content}
                            <div class="chat-timestamp">{formatted_time}</div>
                        </div>
                    </div>
                    """
            
            # Close the chat HTML container (no longer used)
            chat_html += '</div>'
            
            # Create a container for the messages without a duplicate header
            msg_container = st.container()
            
            # Display each message as a separate streamlit component
            with msg_container:
                for message in visible_messages:
                    role = message.get('role', 'unknown')
                    content = message.get('content', '')
                    timestamp = message.get('timestamp', 0)
                    
                    # Format timestamp for display
                    formatted_time = ""
                    if timestamp:
                        try:
                            if isinstance(timestamp, (int, float)):
                                formatted_time = time.strftime('%H:%M:%S', time.localtime(timestamp))
                            elif isinstance(timestamp, str):
                                formatted_time = timestamp
                        except Exception as e:
                            print(f"Error formatting timestamp: {e}")
                    
                    # Process content to escape HTML and handle newlines
                    processed_content = content.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                    
                    # Display using chat_message component with right/left justification
                    if role == 'user':
                        # User messages on the right
                        cols = st.columns([3, 7])  # Push content to the right
                        with cols[1]:
                            # Use a custom container with CSS for right alignment
                            st.markdown(f"""
                            <div style="display: flex; justify-content: flex-end;">
                                <div style="background-color: #E0E7FF; border-radius: 15px 15px 0 15px; 
                                           padding: 10px 15px; max-width: 90%; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                                    <div style="text-align: right; color: #333;">{content}</div>
                                    <div style="font-size: 8px; color: #999; text-align: right; margin-top: 3px;">{formatted_time}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    elif role == 'assistant':
                        # AI messages on the left
                        cols = st.columns([7, 3])  # Push content to the left
                        with cols[0]:
                            # Check if content contains JSON structure for response_data
                            try:
                                # Try to detect if content is or contains JSON
                                if '{' in content and ('"response_data"' in content or '"points"' in content):
                                    # Attempt to extract and parse JSON data
                                    import json
                                    import re
                                    
                                    # Look for JSON in the content
                                    # This regex tries to find a valid JSON object in the text
                                    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                                    if json_match:
                                        json_str = json_match.group(1)
                                        try:
                                            resp_data = json.loads(json_str)
                                            
                                            # Get the points from the response data
                                            formatted_html = '<ul style="margin-left: 5px; padding-left: 15px;">'
                                            
                                            # Check for formatted response_data structure
                                            if 'response_data' in resp_data and isinstance(resp_data['response_data'], dict):
                                                if 'points' in resp_data['response_data'] and resp_data['response_data']['points']:
                                                    # Simple bullet points
                                                    for point in resp_data['response_data']['points']:
                                                        formatted_html += f'<li style="margin-bottom: 5px;">{point}</li>'
                                                
                                                # Check for sections
                                                if 'sections' in resp_data['response_data'] and resp_data['response_data']['sections']:
                                                    for section in resp_data['response_data']['sections']:
                                                        # Add section title
                                                        if 'section_title' in section:
                                                            formatted_html += f'<li style="font-weight: bold; margin-top: 8px;">{section["section_title"]}</li>'
                                                        
                                                        # Add nested bullets
                                                        if 'bullets' in section and section['bullets']:
                                                            formatted_html += '<ul style="margin-left: 10px; padding-left: 15px;">'
                                                            for bullet in section['bullets']:
                                                                formatted_html += f'<li style="margin-bottom: 2px;">{bullet}</li>'
                                                            formatted_html += '</ul>'
                                            # Fallback to simple bullets if no structured data
                                            elif 'points' in resp_data and isinstance(resp_data['points'], list):
                                                for point in resp_data['points']:
                                                    formatted_html += f'<li style="margin-bottom: 5px;">{point}</li>'
                                            else:
                                                # No structured data found, use regular content
                                                formatted_html += f'<li>{content}</li>'
                                                
                                            formatted_html += '</ul>'
                                            
                                            # Use the formatted HTML for the content
                                            content_to_display = formatted_html
                                        except json.JSONDecodeError:
                                            # If JSON parsing fails, fall back to regular content
                                            content_to_display = content
                                    else:
                                        content_to_display = content
                                else:
                                    # No JSON detected, use regular content but convert to bullet points
                                    # Split content by lines and convert to bullets
                                    lines = content.strip().split('\n')
                                    if len(lines) > 1:
                                        formatted_html = '<ul style="margin-left: 5px; padding-left: 15px;">'
                                        for line in lines:
                                            line = line.strip()
                                            if line:
                                                # Check if the line starts with a bullet marker
                                                if line.startswith('- ') or line.startswith('• '):
                                                    bullet_text = line[2:].strip()
                                                else:
                                                    bullet_text = line
                                                formatted_html += f'<li style="margin-bottom: 5px;">{bullet_text}</li>'
                                        formatted_html += '</ul>'
                                        content_to_display = formatted_html
                                    else:
                                        content_to_display = content
                            except Exception as e:
                                print(f"Error parsing response: {e}")
                                content_to_display = content
                            
                            # Use a custom container with CSS for left alignment
                            st.markdown(f"""
                            <div style="display: flex; align-items: flex-start;">
                                <div style="min-width: 30px; height: 30px; margin-right: 8px; background-color: #3F51B5; border-radius: 50%; 
                                         display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 12px;">
                                    <span>AI</span>
                                </div>
                                <div style="background-color: #F0F7FF; border-radius: 15px 15px 15px 0; 
                                           padding: 10px 15px; max-width: 90%; box-shadow: 0 1px 2px rgba(0,0,0,0.1);">
                                    <div style="color: #333;">{content_to_display}</div>
                                    <div style="font-size: 8px; color: #999; text-align: right; margin-top: 3px;">{formatted_time}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    elif role == 'system':
                        # System messages centered
                        cols = st.columns([2, 8, 2])
                        with cols[1]:
                            st.markdown(f"""
                            <div style="display: flex; justify-content: center; margin: 5px 0;">
                                <div style="background-color: #FFFFCC; border-radius: 12px; padding: 5px 12px; 
                                           max-width: 70%; font-style: italic; text-align: center; font-size: 90%;">
                                    <div style="color: #555;">{content}</div>
                                    <div style="font-size: 8px; color: #999; text-align: right; margin-top: 3px;">{formatted_time}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
            
            # Auto-scroll to the bottom using JavaScript
            st.markdown("""
            <script>
                function scrollToBottom() {
                    const chatContainer = document.querySelector('.chat-container');
                    if (chatContainer) {
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                }
                // Call immediately and also after a short delay to ensure DOM is loaded
                scrollToBottom();
                setTimeout(scrollToBottom, 100);
            </script>
            """, unsafe_allow_html=True)
        else:
            st.info("No messages yet. Start by asking a question about your Kubernetes cluster.")
    
    # Render suggested actions in the middle container
    with suggestions_container:
        if st.session_state.current_suggestions:
            # No need for divider or subheader as they're built into the box structure now
            
            # Calculate number of columns based on the number of suggestions
            num_suggestions = len(st.session_state.current_suggestions)
            num_columns = min(3, num_suggestions)  # Maximum 3 columns to ensure buttons are readable
            
            # Create columns for horizontal layout
            cols = st.columns(num_columns)
            
            # Display each suggestion as a button in the appropriate column
            for i, suggestion in enumerate(st.session_state.current_suggestions):
                suggestion_text = suggestion.get('text', f"Suggestion {i+1}")
                suggestion_action = suggestion.get('action', {})
                suggestion_type = suggestion_action.get('type', 'unknown')
                
                # Use modulo to distribute buttons across columns
                col_index = i % num_columns
                
                # Create a button for the suggestion in the appropriate column
                with cols[col_index]:
                    if st.button(suggestion_text, key=f"suggestion_{i}"):
                        # Handle different suggestion types based on the type
                        if suggestion_type == 'run_agent':
                            agent_type = suggestion_action.get('agent_type', 'unknown')
                            with st.spinner(f"Running {agent_type} agent analysis..."):
                                # First add a message to show what action the user selected 
                                user_message = f"Run {agent_type} agent analysis"
                                add_message('user', user_message, investigation_id, db_handler)
                                
                                # Run the agent and get results
                                agent_results = coordinator.run_agent_analysis(
                                    agent_type=agent_type,
                                    namespace=st.session_state.get('selected_namespace', 'default'),
                                    context=st.session_state.get('selected_context', None)
                                )
                                
                                # Add the results to the chat history
                                add_message('assistant', agent_results.get('summary', 
                                                                          f"I've analyzed the {agent_type} data."), 
                                           investigation_id, db_handler)
                                
                                # Store the agent findings if there's an investigation ID
                                if investigation_id and db_handler:
                                    db_handler.add_agent_findings(
                                        investigation_id=investigation_id,
                                        agent_type=agent_type,
                                        findings=agent_results
                                    )
                                    
                                    # Add evidence if available
                                    if 'evidence' in agent_results:
                                        for evidence_type, evidence_data in agent_results.get('evidence', {}).items():
                                            db_handler.add_evidence(
                                                investigation_id=investigation_id,
                                                evidence_type=f"{agent_type}_{evidence_type}",
                                                evidence_data=evidence_data
                                            )
                        
                        elif suggestion_type == 'check_resource':
                            resource_type = suggestion_action.get('resource_type', 'unknown')
                            resource_name = suggestion_action.get('resource_name', 'unknown')
                            
                            with st.spinner(f"Checking {resource_type}/{resource_name}..."):
                                # First add a message to show what action the user selected
                                user_message = f"Check {resource_type}/{resource_name}"
                                add_message('user', user_message, investigation_id, db_handler)
                                
                                # Get resource details
                                resource_details = k8s_client.get_resource_details(
                                    resource_type=resource_type,
                                    resource_name=resource_name,
                                    namespace=st.session_state.get('selected_namespace', 'default')
                                )
                                
                                # Have the coordinator analyze the resource
                                analysis = coordinator.analyze_resource(
                                    resource_type=resource_type,
                                    resource_name=resource_name,
                                    resource_details=resource_details
                                )
                                
                                # Add the results to the chat history
                                add_message('assistant', analysis.get('summary', 
                                                                    f"I've analyzed the {resource_type}/{resource_name} resource."), 
                                           investigation_id, db_handler)
                                
                                # Store the evidence if there's an investigation ID
                                if investigation_id and db_handler:
                                    db_handler.add_evidence(
                                        investigation_id=investigation_id,
                                        evidence_type=f"{resource_type}_details",
                                        evidence_data=resource_details
                                    )
                        
                        elif suggestion_type == 'check_logs':
                            pod_name = suggestion_action.get('pod_name', 'unknown')
                            container_name = suggestion_action.get('container_name', None)
                            
                            with st.spinner(f"Fetching logs for {pod_name}..."):
                                # First add a message to show what action the user selected
                                user_message = f"Check logs for {pod_name}"
                                if container_name:
                                    user_message += f" (container: {container_name})"
                                add_message('user', user_message, investigation_id, db_handler)
                                
                                # Get pod logs
                                logs = k8s_client.get_pod_logs(
                                    pod_name=pod_name,
                                    container_name=container_name,
                                    namespace=st.session_state.get('selected_namespace', 'default')
                                )
                                
                                # Have the coordinator analyze the logs
                                log_analysis = coordinator.analyze_logs(
                                    pod_name=pod_name,
                                    container_name=container_name,
                                    logs=logs
                                )
                                
                                # Add the results to the chat history
                                add_message('assistant', log_analysis.get('summary', 
                                                                        f"I've analyzed the logs for {pod_name}."), 
                                           investigation_id, db_handler)
                                
                                # Store the logs if there's an investigation ID
                                if investigation_id and db_handler:
                                    db_handler.add_evidence(
                                        investigation_id=investigation_id,
                                        evidence_type=f"pod_logs_{pod_name}",
                                        evidence_data=logs
                                    )
                        
                        elif suggestion_type == 'check_events':
                            field_selector = suggestion_action.get('field_selector', None)
                            
                            with st.spinner("Fetching Kubernetes events..."):
                                # First add a message to show what action the user selected
                                user_message = "Check Kubernetes events"
                                if field_selector:
                                    user_message += f" (filter: {field_selector})"
                                add_message('user', user_message, investigation_id, db_handler)
                                
                                # Get events
                                events = k8s_client.get_events(
                                    namespace=st.session_state.get('selected_namespace', 'default'),
                                    field_selector=field_selector
                                )
                                
                                # Have the coordinator analyze the events
                                events_analysis = coordinator.analyze_events(events=events)
                                
                                # Add the results to the chat history
                                add_message('assistant', events_analysis.get('summary', "I've analyzed the Kubernetes events."), 
                                           investigation_id, db_handler)
                                
                                # Store the events if there's an investigation ID
                                if investigation_id and db_handler:
                                    db_handler.add_evidence(
                                        investigation_id=investigation_id,
                                        evidence_type="kubernetes_events",
                                        evidence_data=events
                                    )
                        
                        elif suggestion_type == 'query':
                            query = suggestion_action.get('query', '')
                            
                            # Just add the selected query to the input box
                            st.session_state.user_input = query
                        
                        # Update suggestions based on the action taken, passing accumulated findings
                        update_response = coordinator.update_suggestions_after_action(
                            previous_suggestions=st.session_state.current_suggestions,
                            selected_suggestion_index=i,
                            namespace=st.session_state.get('selected_namespace', 'default'),
                            context=st.session_state.get('selected_context', None),
                            previous_findings=st.session_state.get('accumulated_findings', [])
                        )
                        
                        if update_response:
                            # Add updated suggestions
                            add_suggestions(update_response.get('suggestions', []), investigation_id, db_handler)
                            
                            # Process key findings from the response
                            if 'key_findings' in update_response and isinstance(update_response['key_findings'], list):
                                # Add new key findings to accumulated findings
                                st.session_state.accumulated_findings.extend(update_response['key_findings'])
                                
                                # Keep list size reasonable (last 20 findings)
                                if len(st.session_state.accumulated_findings) > 20:
                                    st.session_state.accumulated_findings = st.session_state.accumulated_findings[-20:]
                                
                                # Persist findings to database if available
                                if investigation_id and db_handler:
                                    db_handler.update_investigation(
                                        investigation_id=investigation_id,
                                        updates={'accumulated_findings': st.session_state.accumulated_findings}
                                    )
                        
                        st.rerun()