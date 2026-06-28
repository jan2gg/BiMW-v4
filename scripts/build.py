# scripts/build.py
"""
Run this script from the project root to build the standalone executable:

    python scripts/build.py

The output will be in dist/BiMW/BiMW.exe
Double-click BiMW.exe to launch without needing Python installed.
"""
import subprocess
import sys
import os

# Make sure we run from the project root regardless of where the script is called from
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

command = [
    sys.executable, "-m", "PyInstaller",
    "--name=BiMW",
    "--windowed",           # no console window on launch
    "--onedir",             # folder output (faster startup than --onefile)
    "--noconfirm",          # overwrite previous build without asking
    "--clean",              # remove temp files before building
    # Hidden imports that PyInstaller misses with PyQtGraph + NI-DAQ
    "--hidden-import=pyqtgraph.graphicsItems.PlotItem",
    "--hidden-import=pyqtgraph.graphicsItems.ViewBox",
    "--hidden-import=nidaqmx._lib",
    "--hidden-import=scipy.signal",
    "--hidden-import=scipy.stats",
    "--hidden-import=sklearn.linear_model",
    "--hidden-import=sklearn.utils._cython_blas",
    "--hidden-import=sklearn.neighbors._typedefs",
    "main.py",
]

print("Building BiMW executable...")
print(f"Working directory: {project_root}")
print()

result = subprocess.run(command)

if result.returncode == 0:
    exe_path = os.path.join(project_root, "dist", "BiMW", "BiMW.exe")
    print()
    print("=" * 50)
    print("Build successful!")
    print(f"Executable: {exe_path}")
    print("Give the entire dist/BiMW/ folder to the researcher.")
    print("=" * 50)
else:
    print()
    print("Build failed. Check the output above for errors.")
    sys.exit(1)