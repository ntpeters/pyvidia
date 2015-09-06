pyvidia
=======
Pyvidia is a script to detect the required driver series (and latest driver
version) for an NVIDIA graphics card in a Linux environment.

The script scrapes device and driver data from `nvidia.com`, so its device and
driver information are always up-to-date.

Inspired by the `nvidia-detect` utility in ELRepo:
http://elrepo.org/tiki/nvidia-detect

#Usage
Pyvidia can either be executed as a standalone script, or imported as a module
in other scripts.

##Script
When executing as a script, the default behavior is to return the required
driver series for the detected NVIDIA device. In the case of current drivers,
the long lived branch is preferred by default over the short lived branch.

The following command line options are also available:
```
--series                Output the required driver series for the detected
                        NVIDIA device [Default]

--latest                Output the latest version number of the driver for the
                        detected NVIDIA device

--longlived             Denotes that the long lived version of the current
                        drivers should be preferred [Default]

--shortlived            Denotes that the short lived version of the current
                        drivers should be preferred.

--deviceid DEVICEID     Provide a device PCI ID to be used instead of auto-
                        detecting one

--url                   Output the download URL for the required driver

-v, --verbose           More detailed output
```

##Import
When imported into another script, there are several available functions:

```
get_required_driver_series(device_id)
    Returns the required driver series for the given or detected NVIDIA device.

    Keyward Args:
    device_id - The device PCI ID to check against the supported devices lists
```

```
get_latest_driver_version(device_id)
    Returns the latest driver version of the required driver series for the
    given or detected NVIDIA device.

    Keyward Args:
    device_id - The device PCI ID to check against the supported devices lists
```

```
get_nvidia_device()
    Returns the device info (name and ID) for the detected NVIDIA device,
    or none if one is not present.
```

```
get_all_supported_devices()
    Returns a dictionary keyed by driver series number, containing the latest
    driver version number and a list of supported devices for that series.
```

```
get_driver_url(device_id)
    Returns the download URL of the required driver for the given or detected
    device.

    Keyward Args:
    device_id - The device PCI ID to check against the supported devices lists
```

#Requirements
The required modules for this script can be installed via pip:
```
pip install -r requirements.txt
```

#Compatibility
Pyvidia should be compatible with both Python 2 (2.7) and Python 3
