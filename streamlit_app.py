import streamlit as st
import requests
import uuid
from datetime import datetime
import psycopg2
import yaml

# Set page config
st.set_page_config(
    page_title="DVD Rental Assistant",
    page_icon="🎬",
    layout="wide"
)

# API URLs
BACKEND_URL = "http://localhost:8000"
TOOLBOX_URL = "http://127.0.0.1:5000"

def load_db_config():
    """Load database configuration from dvdrental_tools.yaml"""
    try:
        with open('dvdrental_tools.yaml', 'r') as file:
            config = yaml.safe_load(file)
            db_config = config['sources']['my-pg-source']
            return {
                "host": db_config['host'],
                "port": db_config['port'],
                "database": db_config['database'],
                "user": db_config['user'],
                "password": db_config['password']
            }
    except Exception as e:
        st.error(f"Error loading database configuration: {e}")
        return None

def check_toolbox_status():
    """Check if the Toolbox server is running"""
    try:
        response = requests.get(f"{TOOLBOX_URL}/api/toolset", timeout=5)
        return response.status_code in [200, 405]
    except requests.exceptions.RequestException:
        return False

def check_backend_status():
    """Check if the Backend server is running"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def get_db_connection():
    """Create a database connection"""
    db_config = load_db_config()
    if not db_config:
        return None
    
    try:
        conn = psycopg2.connect(**db_config)
        return conn
    except psycopg2.Error as e:
        st.error(f"Database connection error: {e}")
        return None

# Initialize session state for chat history and user ID
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())

# Sidebar
with st.sidebar:
    st.title("🎬 DVD Rental Assistant")
    st.markdown("---")
    
    # System Health Status
    st.subheader("🔧 System Health")
    toolbox_status = check_toolbox_status()
    backend_status = check_backend_status()
    db_conn = get_db_connection()
    
    st.markdown("**Toolbox Server:** " + ("🟢 Running" if toolbox_status else "🔴 Stopped"))
    st.markdown("**Backend Server:** " + ("🟢 Running" if backend_status else "🔴 Stopped"))
    st.markdown("**Database:** " + ("🟢 Connected" if db_conn else "🔴 Disconnected"))
    if db_conn:
        db_conn.close()
    
    st.markdown("---")
    
    # Quick Actions
    st.subheader("Quick Actions")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        reset_conversation()
        st.rerun()
    
    # Session Info
    st.subheader("Session Information")
    st.markdown(f"**Session ID:** {st.session_state.user_id[:8]}...")
    
    # About Section
    st.markdown("---")
    st.subheader("ℹ️ About")
    st.markdown("""
    This assistant helps you manage your DVD rental store operations using AI.
    
    **Features:**
    - Film search and recommendations
    - Customer management
    - Rental operations
    - Inventory tracking
    - Analytics and reporting
    """)

# Main content
st.title("🎬 DVD Rental Assistant")
st.markdown("Search for films, manage rentals, and get personalized recommendations.")

# Function to interact with the backend API
def chat_with_backend(message):
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"message": message, "user_id": st.session_state.user_id}
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.RequestException as e:
        st.error(f"Error communicating with backend: {e}")
        return "Sorry, I'm having trouble connecting to the server. Please try again later."

# Function to reset conversation
def reset_conversation():
    # Reset backend context
    try:
        requests.delete(f"{BACKEND_URL}/reset-context/{st.session_state.user_id}")
    except requests.exceptions.RequestException as e:
        st.warning(f"Could not reset backend context: {e}")
    # Clear chat history
    st.session_state.chat_history = []
    # Generate new user ID
    st.session_state.user_id = str(uuid.uuid4())

# Chat interface
chat_container = st.container()
with chat_container:
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

# User input
user_input = st.chat_input("Ask about films...")
if user_input:
    # Add user message to chat history
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.write(user_input)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = chat_with_backend(user_input)
            st.write(response)
    
    # Add AI response to chat history
    st.session_state.chat_history.append({"role": "assistant", "content": response}) 