import subprocess
import sys
import os

def main():
    print("Starting PPMS Measurement Web UI...")
    # Check if we are in the right directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    web_app_path = os.path.join(current_dir, "web_app.py")
    
    if not os.path.exists(web_app_path):
        print(f"Error: {web_app_path} not found.")
        return

    # Run the flask application
    try:
        subprocess.run([sys.executable, web_app_path])
    except KeyboardInterrupt:
        print("\nWeb UI stopped.")

if __name__ == "__main__":
    main()
