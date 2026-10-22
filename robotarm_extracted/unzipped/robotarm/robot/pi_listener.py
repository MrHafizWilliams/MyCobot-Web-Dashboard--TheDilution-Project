# pi_listener.py (Runs constantly on the Raspberry Pi)
import requests
import subprocess
import time
import sys

GCP_VM_URL = "https://izham.redirectme.net/runtask/api/" # <<< UPDATED HTTPS DOMAIN
SCRIPTS_PATH = "/home/er/robotarm/robot/" 
CLIENT_TYPE = "pi" 

# NOTE: For HTTPS with self-signed certs, you might need to use `verify=False` in requests
# (security risk) OR install the root certificate authority on the Pi system.

def send_status(log_id, status_message, message=""):
    """Posts the current status for the PI client."""
    try:
        data = {'log_id': log_id, 'new_status': status_message, 'client_type': CLIENT_TYPE, 'message': message}
        # If using a self-signed cert, requests.post(..., verify=False) may be needed.
        response = requests.post(GCP_VM_URL + "update_status.php", data=data)
        response.raise_for_status()
        print(f"{CLIENT_TYPE} Status reported for ID {log_id}: {status_message}")
    except requests.exceptions.RequestException as e:
        print(f"Error reporting status for ID {log_id}: {e}")

def check_and_run():
    try:
        # Polling the PI-specific endpoint
        response = requests.get(GCP_VM_URL + "check_pi_command.php") 
        response.raise_for_status() 
        data = response.text.strip() 

        if data and data != "none":
            try:
                # Expecting log_id|command|message
                parts = data.split('|', 2) 
                if len(parts) < 3:
                     # Handle case where message is NULL/empty
                     log_id, command = parts[0], parts[1]
                     task_message = ""
                else:
                    log_id, command, task_message = parts
                    
                log_id = int(log_id)
            except ValueError:
                print(f"Received malformed command data: {data}")
                return 

            print(f"Command received (ID {log_id}): {command}")
            print(f"Task Message: {task_message}")
            
            send_status(log_id, "RUNNING")
            
            script_path = f"{SCRIPTS_PATH}{command}.py"
            
            try:
                # Pass the message as a second command-line argument to the task script
                subprocess.run(["python3", script_path, str(log_id), task_message], check=True)
                
            except subprocess.CalledProcessError as e:
                error_msg = f"Task script failed with code {e.returncode}."
                print(error_msg)
                send_status(log_id, "ERROR", error_msg)
                
    except requests.exceptions.RequestException as e:
        print(f"Error communicating with GCP VM: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    while True:
        check_and_run()
        time.sleep(5)
