# ====================================================================================================
# P02_system_processes.py
# ====================================================================================================

# ====================================================================================================
# Import Libraries that are required to adjust sys path
# ====================================================================================================
import sys                      # Provides access to system-specific parameters and functions
from pathlib import Path        # Offers an object-oriented interface for filesystem paths

# Adjust sys.path so we can import modules from the parent folder
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.dont_write_bytecode = True  # Prevents _pycache_ creation

# Import Project Libraries
from processes.P00_set_packages import *

# ====================================================================================================
# Import shared functions and file paths from other folders
# ====================================================================================================



# ====================================================================================================
# Functions to detect Operating System
# ====================================================================================================

def detect_os() -> str:
    """
    Detect the current operating environment.

    Returns:
        - "Windows"           : Running under native Windows Python.
        - "Windows (WSL)"     : Running under WSL (Linux kernel with Microsoft signature).
        - "Linux"             : Running under a non-WSL Linux.
        - "iOS"               : Running under Python on iOS (e.g. Pythonista, Pyto).
    """
    # 1) Native Windows
    if sys.platform == "win32":
        return "Windows"

    # 2) Darwin-based (macOS or iOS)
    if sys.platform == "darwin":
        machine = platform.machine() or ""
        # iOS devices often report machine names beginning with "iP" (iPhone/iPad)
        if machine.startswith(("iP",)):
            return "iOS"
        # Fallback: treat any other Darwin as macOS (or generic Darwin)
        return "macOS"

    # 3) Linux or WSL
    if sys.platform.startswith("linux"):
        release = platform.uname().release.lower()
        # WSL-identifiers in the Linux kernel release string
        if "microsoft" in release or "wsl" in release:
            return "Windows (WSL)"
        return "Linux"

    # 4) Anything else
    return sys.platform

# ====================================================================================================
# Functions to derive User's Download Folder
# ====================================================================================================

def user_download_folder() -> Path:
    """
    Return the current user's Downloads folder based on the OS.
    """
    os_type = detect_os()

    if os_type == "Windows":
        # Windows user profile Downloads
        return Path(f"C:/Users/{getpass.getuser()}/Downloads")

    elif os_type == "Windows (WSL)":
        # WSL has no real Downloads folder, so fallback to Linux home
        return Path.home() / "Downloads"

    elif os_type == "macOS":
        # macOS standard Downloads folder
        return Path.home() / "Downloads"

    elif os_type == "Linux":
        # Generic Linux, use home Downloads
        return Path.home() / "Downloads"

    elif os_type == "iOS":
        # iOS doesn’t have a standard Downloads folder
        return Path.home()

    else:
        # Fallback
        return Path.home()

# ====================================================================================================
# Run Main Script
# ====================================================================================================

if __name__ == "__main__":
    print(f"Detected OS: {detect_os()}")
    print(f"Download folder: {user_download_folder()}")