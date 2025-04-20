"""
Fix for the chatbot interface suggestion rendering.

This file contains the improved code for rendering suggestions in the chatbot interface.
This ensures that suggestions properly correlate with AI responses.
"""

# The issue is likely in how the suggestions are displayed in the UI.
# The solution is to ensure that suggestions are properly rendered after each interaction.

# 1. Original way the suggestions are added:
# suggestions = response.get('suggestions', [])
# add_suggestions(suggestions, investigation_id, db_handler)

# 2. Problem: When a user asks a question, the response includes suggestions in the 'suggestions' field,
#    but the UI might not be properly updated to show these new suggestions.

# 3. Solution: Make sure we're always updating session state with the latest suggestions
#    and triggering a UI refresh after adding them.

# Here's the fix to apply to components/chatbot_interface.py:

"""
def add_suggestions(suggestions: List[Dict[str, Any]], investigation_id: Optional[str] = None, db_handler = None):
    """
    Add suggested next actions to the chatbot interface.
    
    Args:
        suggestions: List of suggestion objects with 'text' and 'action' keys
        investigation_id: Optional investigation ID to persist the suggestions
        db_handler: Optional database handler to persist the suggestions
    """
    # Update the session state with the latest suggestions
    st.session_state.current_suggestions = suggestions
    
    # Persist to database if provided
    if investigation_id and db_handler:
        db_handler.update_next_actions(
            investigation_id=investigation_id,
            next_actions=suggestions
        )

# In the process_user_input part:
# After getting a response from the coordinator, ensure suggestions are added

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
        
        # Generate suggested next actions
        suggestions = response.get('suggestions', [])
        add_suggestions(suggestions, investigation_id, db_handler)
        
        # Add assistant response to history
        # Implementation continues...

# When rendering the suggestions:
with suggestions_container:
    if st.session_state.current_suggestions:
        st.subheader("Suggested Next Actions")
        
        # Display each suggestion as a button
        for i, suggestion in enumerate(st.session_state.current_suggestions):
            suggestion_text = suggestion.get('text', f"Suggestion {i+1}")
            suggestion_action = suggestion.get('action', {})
            suggestion_type = suggestion_action.get('type', 'unknown')
            
            # Add priority badge
            priority = suggestion.get('priority', 'NORMAL')
            if priority == 'CRITICAL':
                badge = "🔴"
            elif priority == 'HIGH':
                badge = "🟠"
            else:
                badge = "🟢"
                
            # Show the suggestion with priority badge
            if st.button(f"{badge} {suggestion_text}", key=f"suggestion_{i}"):
                # Handle the suggestion...
"""