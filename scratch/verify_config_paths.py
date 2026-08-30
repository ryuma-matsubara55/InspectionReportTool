
import sys
import os
from pathlib import Path

# Simulate sys.frozen
sys.frozen = True
sys.executable = r"C:\Path\To\YourApp.exe"

# Logic from modified config.py
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCES_DIR = Path(getattr(sys, '_MEIPASS', str(BASE_DIR))) / "resources"
else:
    BASE_DIR = Path(__file__).resolve().parent
    RESOURCES_DIR = BASE_DIR / "resources"

print(f"Frozen: {getattr(sys, 'frozen', False)}")
print(f"Executable: {sys.executable}")
print(f"BASE_DIR: {BASE_DIR}")
print(f"RESOURCES_DIR: {RESOURCES_DIR}")

# Test non-frozen
sys.frozen = False
if getattr(sys, 'frozen', False):
    BASE_DIR_2 = Path(sys.executable).resolve().parent
else:
    BASE_DIR_2 = Path(__file__).resolve().parent

print(f"Non-frozen BASE_DIR: {BASE_DIR_2}")
