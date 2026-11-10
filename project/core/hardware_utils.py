import platform
import subprocess
import hashlib
import uuid

def get_hardware_id() -> str:
    """
    Generates a unique, stable Hardware ID (HWID) for the current machine.
    Uses platform-specific commands to get motherboard UUIDs when possible,
    falling back to MAC address.
    """
    hwid = ""
    os_name = platform.system().lower()
    
    try:
        if os_name == "windows":
            # Best approach on Windows: get MachineGuid from Registry
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                    hwid, _ = winreg.QueryValueEx(key, "MachineGuid")
            except Exception:
                # Fallback to wmic
                result = subprocess.check_output(
                    "wmic csproduct get uuid", 
                    shell=True, 
                    stderr=subprocess.STDOUT,
                    text=True
                )
                lines = result.strip().split("\n")
                if len(lines) > 1:
                    hwid = lines[1].strip()
        elif os_name == "darwin":
            # Best approach on macOS: get hardware UUID from system_profiler
            result = subprocess.check_output(
                "system_profiler SPHardwareDataType | grep 'Hardware UUID'",
                shell=True,
                stderr=subprocess.STDOUT,
                text=True
            )
            if ":" in result:
                hwid = result.split(":")[1].strip()
        elif os_name == "linux":
            # Best approach on Linux: read machine-id
            with open("/etc/machine-id", "r") as f:
                hwid = f.read().strip()
    except Exception:
        pass
        
    if not hwid or len(hwid) < 5:
        # Fallback to python's uuid.getnode() which is based on the MAC address
        mac = uuid.getnode()
        hwid = str(mac)
        
    # Hash the resulting string to get a standard length alphanumeric string
    return hashlib.sha256(hwid.encode('utf-8')).hexdigest()[:32]
