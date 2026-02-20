import subprocess
import re

def check_tools():
    tools = ["adb", "fastboot"]
    missing = []
    for tool in tools:
        try:
            subprocess.run([tool, "--version"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(tool)
    return missing

def get_devices():
    devices = []
    # Scan ADB
    try:
        adb_proc = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        for line in adb_proc.stdout.splitlines()[1:]:
            if "device" in line and not "offline" in line:
                serial = line.split()[0]
                devices.append({"type": "ADB", "serial": serial})
    except: pass
    
    # Scan Fastboot
    try:
        fb_proc = subprocess.run(["fastboot", "devices"], capture_output=True, text=True)
        for line in fb_proc.stdout.splitlines():
            if line.strip():
                serial = line.split()[0]
                devices.append({"type": "FASTBOOT", "serial": serial})
    except: pass
    return devices

def fetch_partitions_from_device(serial):
    cmd = ["fastboot", "-s", serial, "getvar", "all"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = proc.stderr # getvar all output often goes to stderr
        
        partitions = set()
        pattern = re.compile(r"partition-(?:size|type):([^:]+):")
        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                partitions.add(match.group(1))
        return sorted(list(partitions))
    except:
        return []
