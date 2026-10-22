import requests
import time
import sys
import subprocess 

GCP_VM_URL = "https://robot.thedilution.my/api/" # <<< UPDATED HTTPS DOMAIN
ROBOT_SCRIPT_PATH = "/home/er/robotarm/moverobotarm.py" # <<< UPDATE PATH
CLIENT_TYPE = "pi" 

def send_final_status(log_id, final_status, message=""):
    """Posts final status for the PI client."""
    try:
        data = {'log_id': log_id, 'new_status': final_status, 'client_type': CLIENT_TYPE, 'message': message} 
        response = requests.post(GCP_VM_URL + "update_status.php", data=data)
        response.raise_for_status()
        print(f"Task {log_id} completed. Status: {final_status}.")
    except requests.exceptions.RequestException as e:
        print(f"Error reporting final status for ID {log_id}: {e}")


def main():
    if len(sys.argv) < 2:
        print("Error: Task script requires log_id as argument.")
        sys.exit(1)
        
    log_id = int(sys.argv[1])
    
    try:
        result = subprocess.run(
            ["python3", ROBOT_SCRIPT_PATH], 
            capture_output=True,
            text=True,
            check=True
        )
        
        send_final_status(log_id, "FINISHED")
            
    except subprocess.CalledProcessError as e:
        error_message = f"Robot arm failed (Code {e.returncode}). Output: {e.stderr.strip()}"
        send_final_status(log_id, "BROKEN", message=error_message)
        sys.exit(1)
        
    except FileNotFoundError:
        error_message = f"Execution path error. Script not found: {ROBOT_SCRIPT_PATH}"
        send_final_status(log_id, "ERROR", message=error_message)
        sys.exit(1)
        
    except Exception as e:
        error_message = f"Critical Python Error: {e}"
        send_final_status(log_id, "ERROR", message=error_message)
        sys.exit(1)

if __name__ == "__main__":
    main()

