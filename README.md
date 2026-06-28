# BiMW Modulation Software v4

Control, acquisition, and post-processing software for **BiMW photonic biosensor** experiments.

The application is built with Python 3.12, PyQt6, PyQtGraph, and NI-DAQmx. It provides a desktop interface for:
- calibrating the modulation working points,
- acquiring live phase measurements from the biosensor setup,
- loading and filtering saved experiment data.

## Overview

BiMW Modulation Software is intended for laboratory use with a National Instruments DAQ connected to a BiMW photonic biosensor system.

The software is organized into three main workflows:
1. **Calibration**: configure the device and modulation, start the laser, and compute calibration points.
2. **Measurement**: acquire live photodiode signals, compute the unwrapped phase, and save the experiment to disk.
3. **Processing**: load a saved experiment file, apply offline filtering, and export processed results.

## For lab users

### Run the application

On the lab machine, launch:

```text
dist/BiMW/BiMW.exe
```

No Python installation is required to run the packaged executable.

### Lab machine requirements

Before running the application, make sure the machine has:
- a supported National Instruments DAQ connected,
- NI-DAQmx installed (NI-DAQmx 2022 or newer),
- access to the full packaged application folder.

### Important deployment note

Do **not** copy only `BiMW.exe`.  
Copy the entire `dist/BiMW/` folder to the target machine, because the executable depends on the additional files generated alongside it.

## Measurement workflow

### 1. Calibration tab

Typical sequence:
1. Select the DAQ device.
2. Select modulation type and current range.
3. Set frequency, laser current, and calibration time.
4. Click **Start Laser**.
5. Click **Calibration** and wait until the process finishes.

When calibration succeeds, the software stores the calibration points and enables the measurement workflow.

### 2. Measure tab

Typical sequence:
1. Confirm calibration has been completed.
2. Click **Start Laser**.
3. Choose where to save the measurement `.DAT` file.
4. Let the acquisition run while the phase is displayed live.
5. Click **Stop** when the experiment is complete.

The measurement file stores time and phase values for the available channels.

### 3. Processing tab

Typical sequence:
1. Load a saved experiment file.
2. Apply the offline low-pass filter if needed.
3. Save the processed result to a new `.DAT` file.

This step is intended for post-acquisition cleanup and analysis of previously recorded data.

## Data files

The software uses tab-separated `.DAT` files for saved measurements and processed outputs.

Typical saved data includes:
- time in seconds,
- phase values in radians for each channel.

Snapshot exports and processed files are also written as tab-separated text data so they can be inspected later in Python, MATLAB, Excel, or similar tools.

## Developer setup

### Python environment

The current local development environment is:

```text
C:\venvs\BiMW-v4\
```

To activate it:

```bat
C:\venvs\BiMW-v4\Scripts\activate
```

To recreate it from scratch:

```bat
py -3.12 -m venv C:\venvs\BiMW-v4
C:\venvs\BiMW-v4\Scripts\activate
pip install -r requirements.txt
```

If a different local path is preferred, create the virtual environment elsewhere and adjust the activation command accordingly.

### Run in development mode

```bat
C:\venvs\BiMW-v4\Scripts\activate
python main.py
```

### Run tests

```bat
python -m pytest tests/ -v
```

### Build the executable

```bat
python scripts/build.py
```

Expected output:

```text
dist/BiMW/BiMW.exe
```

After building, distribute the entire `dist/BiMW/` directory.

## Project structure

```text
BiMW-v4/
├── main.py                             # Application entry point
├── controllers/                        # UI <-> application logic
│   ├── main_controller.py              # Top-level application orchestration
│   ├── calibration_controller.py       # Calibration tab logic
│   ├── measurement_controller.py       # Measurement tab logic
│   ├── processing_controller.py        # Offline processing tab logic
│   ├── intensity_controller.py         # Intensity pre-check workflow
│   ├── measurement_setup_controller.py # Shared device/modulation setup
│   └── data_controller.py              # File dialogs and data I/O
├── core/
│   ├── daq/                            # NI-DAQ wrappers and setup
│   │   ├── acquisition.py              # Read/write task handling
│   │   ├── daq_setup.py                # Channel/timing configuration
│   │   └── device_discovery.py         # Device listing and constants
│   └── signal/                         # Signal generation and processing
│       ├── signal_generation.py        # Sine, sawtooth, no modulation
│       ├── signal_filter.py            # Filter builders and helpers
│       └── sr_processor.py             # SR signal, calibration, phase logic
├── models/                             # Application state and configuration
│   ├── measurement_config.py           # Measurement parameters
│   ├── calibration_result.py           # Calibration output
│   └── acquisition_state.py            # Live acquisition state
├── services/                           # Shared utility services
│   ├── logger_service.py               # Logging service
│   └── timer_service.py                # QTimer wrapper
├── views/                              # PyQt6 UI classes
│   ├── main_window.py                  # Main window and tab container
│   ├── tab_calibration.py              # Calibration tab UI
│   ├── tab_measure.py                  # Measurement tab UI
│   ├── tab_processing.py               # Processing tab UI
│   └── tab_intensity.py                # Intensity tab UI
├── Lib/                                # Shared constants
│   ├── Colors.py                       # Chart colors
│   └── Strings.py                      # String constants
├── scripts/
│   └── build.py                        # Build helper
├── tests/
│   └── test_core.py                    # Core signal-processing tests
└── README.md
```

## Logging and troubleshooting

Runtime events and errors are written to:

```text
log.txt
```

If the application fails to start, cannot see the DAQ, or reports an acquisition error, check this file first.

Common things to verify:
- NI-DAQmx is installed correctly.
- The DAQ device is connected and visible to the system.
- The correct device is selected in the interface.
- No other process is currently holding the DAQ task.

## Notes for maintenance

When modifying the application:
- keep hardware-access logic inside `core/daq/`,
- keep signal-processing logic inside `core/signal/`,
- keep UI widgets in `views/` free of business logic,
- keep controller classes focused on coordination between the UI and the backend.

This separation makes the codebase easier to test, debug, and extend.

## Status

Current version: **v4**

This repository contains the active desktop application used for BiMW modulation calibration, measurement, and processing workflows.