import datetime
import os

def save_session_log(logs):
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/session_{timestamp}.txt"
    
    with open(filename, "w") as f:
        for line in logs:
            f.write(f"{line}\n")
    return filename

def start_boot_monitor(serial):
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logs/bootlog_{timestamp}.txt"
    
    return filename
