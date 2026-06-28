# core/daq/device_discovery.py
NO_DEVICE = "No Device"
RELOAD_DEVICES = "Reload devices..."


def get_available_devices() -> list[str]:
    """Return a list of NI-DAQ device names found on the system.
    Returns ['No Device'] when nidaqmx is unavailable or no hardware
    is connected — safe to call on any machine."""
    try:
        import nidaqmx
        import nidaqmx.system
        system = nidaqmx.system.System.local()
        devices = [device.name for device in system.devices]
        if not devices:
            devices.append(NO_DEVICE)
        return devices
    except Exception:
        # nidaqmx not installed, driver missing, or no hardware
        return [NO_DEVICE]