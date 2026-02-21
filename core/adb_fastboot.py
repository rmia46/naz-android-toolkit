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
            elif "sideload" in line:
                serial = line.split()[0]
                devices.append({"type": "SIDELOAD", "serial": serial})
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

def get_adb_info(serial):
    info = {"Model": "N/A", "Build": "N/A", "Root": "No"}
    try:
        # Get Model
        model_proc = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.product.model"], capture_output=True, text=True)
        info["Model"] = model_proc.stdout.strip()
        
        # Get Build
        build_proc = subprocess.run(["adb", "-s", serial, "shell", "getprop", "ro.build.display.id"], capture_output=True, text=True)
        info["Build"] = build_proc.stdout.strip()
        
        # Check Root
        root_proc = subprocess.run(["adb", "-s", serial, "shell", "id"], capture_output=True, text=True)
        if "uid=0(root)" in root_proc.stdout:
            info["Root"] = "Yes"
    except: pass
    return info

def get_adb_metrics(serial):
    metrics = {"Battery": "N/A", "Temp": "N/A", "Storage": "N/A"}
    try:
        # Battery & Temp
        batt_proc = subprocess.run(["adb", "-s", serial, "shell", "dumpsys", "battery"], capture_output=True, text=True)
        batt_out = batt_proc.stdout
        level = re.search(r"level:\s*(\d+)", batt_out)
        temp = re.search(r"temperature:\s*(\d+)", batt_out)
        if level: metrics["Battery"] = f"{level.group(1)}%"
        if temp: metrics["Temp"] = f"{int(temp.group(1))/10}°C"
        
        # Storage (Internal)
        storage_proc = subprocess.run(["adb", "-s", serial, "shell", "df", "/data"], capture_output=True, text=True)
        lines = storage_proc.stdout.splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 5:
                metrics["Storage"] = f"{parts[4]} used" # e.g. 45%
    except: pass
    return metrics

def get_fastboot_info(serial):
    info = {"Product": "N/A", "Unlocked": "N/A"}
    try:
        proc = subprocess.run(["fastboot", "-s", serial, "getvar", "all"], capture_output=True, text=True, timeout=3)
        output = proc.stderr
        
        product_match = re.search(r"product:\s*(.*)", output)
        if product_match: info["Product"] = product_match.group(1).strip()
        
        unlocked_match = re.search(r"unlocked:\s*(.*)", output)
        if unlocked_match: info["Unlocked"] = unlocked_match.group(1).strip()
    except: pass
    return info

def fetch_partitions_from_device(serial):
    cmd = ["fastboot", "-s", serial, "getvar", "all"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        output = proc.stderr
        
        found = set()
        pattern1 = re.compile(r"partition-(?:size|type):([^:]+):")
        pattern2 = re.compile(r"\(bootloader\)\s*partition-.*:([^:]+)")
        
        for line in output.splitlines():
            match1 = pattern1.search(line)
            if match1: found.add(match1.group(1).strip())
            match2 = pattern2.search(line)
            if match2: found.add(match2.group(1).strip())
        
        # Categorization Logic
        categories = {
            "Standard": [],
            "Critical/Advanced": []
        }
        
        # Partitions usually safe/common to flash
        standard_names = [
            "boot", "recovery", "system", "vendor", "super", "userdata", "dtbo", 
            "vbmeta", "vbmeta_system", "vbmeta_vendor", "odm", "product", "system_ext",
            "my_product", "my_engineering", "my_stock", "my_heytap", "my_company", 
            "my_carrier", "my_region", "my_preload", "my_manifest"
        ]
        
        for p in found:
            # Skip hex addresses (e.g. 0x1000)
            if p.startswith("0x") or len(p) < 2:
                continue
                
            is_standard = any(std in p.lower() for std in standard_names)
            if is_standard:
                categories["Standard"].append(p)
            else:
                categories["Critical/Advanced"].append(p)
        
        categories["Standard"].sort()
        categories["Critical/Advanced"].sort()
        return categories
    except:
        return {"Standard": [], "Critical/Advanced": []}

