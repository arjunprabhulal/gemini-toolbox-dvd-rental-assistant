import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path

def run_backend():
    """Run the FastAPI backend server"""
    try:
        subprocess.run([sys.executable, "backend.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running backend: {e}")
        sys.exit(1)

def run_frontend():
    """Run the Streamlit frontend server"""
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running frontend: {e}")
        sys.exit(1)

def main():
    # Check if .env file exists
    if not Path(".env").exists():
        print("Error: .env file not found!")
        print("Please create a .env file with your configuration.")
        print("You can use .env.example as a template.")
        sys.exit(1)

    print("Starting Gemini Toolbox DVD Rental Assistant...")
    print("Press Ctrl+C to stop all servers")

    backend_process = None
    frontend_process = None

    try:
        # Start backend server in a separate process with --no-open-browser flag
        backend_process = subprocess.Popen([sys.executable, "backend.py", "--no-open-browser"])
        print("Backend server started on http://localhost:8000")
        
        # Wait for backend to start
        time.sleep(2)
        
        # Start frontend server in a separate process
        frontend_process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8501"])
        print("Frontend server started on http://localhost:8501")
        
        # Open the frontend in the default browser
        webbrowser.open("http://localhost:8501")
        
        # Wait for both processes
        backend_process.wait()
        frontend_process.wait()
        
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        if backend_process:
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        if frontend_process:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
        print("Servers stopped")
    except Exception as e:
        print(f"Error: {e}")
        if backend_process:
            backend_process.terminate()
        if frontend_process:
            frontend_process.terminate()
        sys.exit(1)
    finally:
        # Ensure processes are terminated
        if backend_process and backend_process.poll() is None:
            backend_process.terminate()
        if frontend_process and frontend_process.poll() is None:
            frontend_process.terminate()

if __name__ == "__main__":
    main() 