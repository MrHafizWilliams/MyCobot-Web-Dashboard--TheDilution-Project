import requests
import subprocess
import time
import sys

# Configuration
GCP_VM_URL = "https://robot.thedilution.my/api/"
SCRIPTS_PATH = "/home/er/robotarm/"
CLIENT_TYPE = "pi"

def send_status(log_id, status_message, message=""):
    """Posts the current status for the PI client."""
    try:
        data = {'log_id': log_id, 'new_status': status_message, 'client_type': CLIENT_TYPE, 'message': message}
        # Verify=False used if you have self-signed cert issues, otherwise remove it
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
                log_id_str, command = data.split('|', 1)
                log_id = int(log_id_str)
            except ValueError:
                print(f"Received malformed command data: {data}")
                return

            print(f"Command received (ID {log_id}): {command}")

            # --- NEW FIX: CHECK FOR ANGLE COMMANDS ---
            if command.startswith("ANGLE:"):
                print(f" -> Identifying Sync Command. Skipping execution.")
                # We mark it as FINISHED so the DB doesn't keep serving it to us
                send_status(log_id, "FINISHED", "Skipped: Unity Sync Data")
                return
            # -----------------------------------------

            send_status(log_id, "RUNNING")
            
            # Construct the script path (e.g., /home/pi/robotarm/task1.py)
            script_path = f"{SCRIPTS_PATH}{command}.py"

            try:
                # Pass log_id as an argument to the task script
                subprocess.run(["python3", script_path, str(log_id)], check=True)
                
                # Note: The task script usually updates status to FINISHED, 
                # but if your task scripts don't, you might want to uncomment the line below:
                # send_status(log_id, "FINISHED", "Task Script Completed")

            except subprocess.CalledProcessError as e:
                error_msg = f"Task script failed with code {e.returncode}."
                print(error_msg)
                send_status(log_id, "ERROR", error_msg)
            except FileNotFoundError:
                error_msg = f"Script file not found: {script_path}"
                print(error_msg)
                send_status(log_id, "ERROR", error_msg)

    except requests.exceptions.RequestException as e:
        print(f"Error communicating with GCP VM: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    print("Pi Listener Started... Waiting for commands.")
    while True:
        check_and_run()
        time.sleep(5)
