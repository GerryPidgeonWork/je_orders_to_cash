# ====================================================================================================
# P00_set_packages.py
# ====================================================================================================

# Centralized import file that sets up all global packages used across the project. Ensures consistent imports and prevents duplication across modules.

# --- Standard library imports (no installation required) ---
import os                                                       # Operating system functions (paths, environment variables)
import re                                                       # Regular expressions for text pattern matching
import csv                                                      # Read/write CSV files
import time                                                     # Time utilities (e.g., sleep/delays)
import getpass                                                  # Securely get current user's login name
import threading                                                # Run code concurrently using threads
import queue                                                    # Thread-safe FIFO queue for communication between threads
import tkinter as tk                                            # Standard Python GUI toolkit
import datetime as dt
import traceback
from datetime import date, datetime, timedelta                  # Date and time handling
from urllib.parse import (                                      # URL utilities (parsing & building URLs safely)
    urljoin,                                                    # Join base + relative URLs
    urlparse,                                                   # Parse URL into components
    urlunparse,                                                 # Rebuild URL from components
    parse_qs,                                                   # Parse query string (?page=2)
    urlencode)                                                  # Build query strings
from tkinter import ttk, messagebox, filedialog                 # Tkinter extras: themed widgets, popup dialogs, file picker
from typing import Iterable, Callable, Optional, List, Dict     # Type hinting for cleaner function definitions
from dataclasses import dataclass                               # Create structured classes easily without boilerplate code

# --- Third-party imports (require installation) ---
import pandas as pd                                             # (pip install pandas) Data analysis and CSV/file handling
import numpy as np                                              # (Installed with pandas) Numerical operations and arrays
import pdfplumber                                               # (pip install pdfplumber) Extract text/tables from PDF files accurately
from pdfminer.high_level import extract_text                    # (Installed with pdfplumber) Fallback PDF text extraction if pdfplumber fails
from tkcalendar import DateEntry                                # (pip install tkcalendar) Calendar drop down for GUI element