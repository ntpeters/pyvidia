#!/usr/bin/env python

# Pyvidia
# Gets the required driver series for the detected NVIDIA device.
# Also able to get the latest version of the required driver series.
# Parses the list of supported devices for each driver version from the NVIDIA site.

import argparse
import collections
import re
import subprocess
import sys
import urllib2
from bs4 import BeautifulSoup
from bs4 import NavigableString

legacy_device_url = "http://www.nvidia.com/object/IO_32667.html"
unix_driver_url = "http://www.nvidia.com/object/unix.html"
long_lived_url = ""
short_lived_url = ""
long_lived_version = ""
short_lived_version = ""
legacy_versions = []

series_lookup = None

device = collections.namedtuple("Device", ["name", "pci_id"])

verbose = False
prefer_long_lived = True

def __is_driver_section_header(tag):
    """
    Returns true if the given tag is a driver version section header.

    Keyword Args:
    tag -- The HTML tag to inspect
    """
    for child in tag.children:
        if ".xx driver" in child:
            return True
    return False

def __get_driver_section_headers():
    """
    Returns all driver version section header tags on the legacy driver page.
    """
    legacy_device_page = urllib2.urlopen(legacy_device_url)
    soup = BeautifulSoup(legacy_device_page)
    return soup.find_all(__is_driver_section_header)

def __get_driver_series_tag_text(tag):
    """
    Returns the driver series number from the given HTML tag

    Keyword Args:
    tag -- Device driver section header tag
    """
    driver_regex = re.compile('[0-9]+\.?[0-9]*\.?[0-9]*')
    match = driver_regex.search(tag.text)
    if match:
        match_text = tag.text[match.start():match.end()]
        if match_text[-1:] == ".":
            match_text = match_text[:-1]
        return match_text
    return None

def __get_driver_series_supported_devices(tag):
    """
    Returns the list of supported devices for the given driver section

    Keyword Args:
    tag -- Device driver section header tag
    """
    devices = []

    table = tag.parent.next_sibling.next_sibling
    rows = table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) >= 2:
            if "GPU product" not in cols[0].text and "Device" not in cols[0].text:
                device_name = cols[0].text
                pci_id_regex = re.compile("[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]")
                pci_id_match = pci_id_regex.search(cols[1].text)
                if pci_id_match:
                    pci_id = cols[1].text[pci_id_match.start():pci_id_match.end()]
                    device_info = device(name=device_name, pci_id=pci_id)
                    devices.append(device_info)

    return devices

def __get_current_driver_supported_devices(url):
    """
    Returns the list of supported devices for the current driver at the given URL.

    Keyword Args:
    url -- URL to the page of supported devices for a current driver
    """
    devices = []

    page = urllib2.urlopen(url)
    soup = BeautifulSoup(page)

    current_sections = soup.find_all("div", {"class":"informaltable"}, limit=5)
    for section in current_sections:
        rows = section.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                device_name = cols[0].text
                pci_id = cols[1].text.split(' ')[0]
                device_info = device(name=device_name, pci_id=pci_id)
                devices.append(device_info)

    return devices

def __load_latest_version_numbers():
    """
    Fetches the latest version numbers for each driver series.
    """
    global long_lived_version
    global short_lived_version
    global long_lived_url
    global short_lived_url
    global legacy_versions

    page = urllib2.urlopen(unix_driver_url)
    soup = BeautifulSoup(page)

    driver_section = None

    p_tags = soup.find_all('p')
    for p_tag in p_tags:
        section_header = p_tag.find('strong')
        if section_header and "Linux x86" in section_header.text:
            driver_section = p_tag
            break

    long_lived_version = ""
    short_lived_version = ""
    legacy_versions = []
    if driver_section:
        long_lived_found = False
        short_lived_found = False
        legacy_found = False
        for child in driver_section.children:
            if isinstance(child, NavigableString):
                if "Long Lived" in str(child):
                    long_lived_found = True
                elif "Short Lived" in str(child):
                    short_lived_found = True
                elif ".xx series" in str(child):
                    legacy_found = True
            elif child.name == "a":
                if long_lived_found and long_lived_version == "":
                    long_lived_version = child.text
                elif short_lived_found and short_lived_version == "":
                    short_lived_version = child.text
                elif legacy_found:
                    legacy_versions.append(child.text)
                    legacy_found = False

    # Compose the URLs for the current version driver support pages
    long_lived_url = "http://us.download.nvidia.com/XFree86/Linux-x86_64/" + long_lived_version  + "/README/supportedchips.html"
    short_lived_url = "http://us.download.nvidia.com/XFree86/Linux-x86_64/" + short_lived_version  + "/README/supportedchips.html"

def get_all_supported_devices():
    """
    Returns a dictionary of keyed by driver series number, containing the latest
    driver version number and a list of supported devices for that series.
    """
    global series_lookup
    series_lookup = collections.defaultdict(dict)

    __load_latest_version_numbers()

    driver_headers = __get_driver_section_headers()
    for header in driver_headers:
        series = __get_driver_series_tag_text(header)
        devices = __get_driver_series_supported_devices(header)
        for device in devices:
            latest_version = ""
            for legacy_version in legacy_versions:
                if series in legacy_version:
                    latest_version = legacy_version
                    break

            try:
                series_lookup[series]["latest_version"]
            except KeyError:
                series_lookup[series]["latest_version"] = latest_version
                pass

            try:
                series_lookup[series]["devices"]
            except KeyError:
                series_lookup[series]["devices"] = []
                pass

            series_lookup[series]["devices"].append(device)

    long_lived_series = ".".join(long_lived_version.split(".")[0:-1])
    short_lived_series = ".".join(short_lived_version.split(".")[0:-1])

    try:
        series_lookup[long_lived_series]["latest_version"]
    except KeyError:
        series_lookup[long_lived_series]["latest_version"] = long_lived_version
        pass
    try:
        series_lookup[short_lived_series]["latest_version"]
    except KeyError:
        series_lookup[short_lived_series]["latest_version"] = short_lived_version
        pass

    try:
        series_lookup[long_lived_series]["devices"]
    except KeyError:
        series_lookup[long_lived_series]["devices"] = []
        pass
    try:
        series_lookup[short_lived_series]["devices"]
    except KeyError:
        series_lookup[short_lived_series]["devices"] = []

    long_lived_devices = __get_current_driver_supported_devices(long_lived_url)
    short_lived_devices = __get_current_driver_supported_devices(short_lived_url)
    for l_device, s_device in zip(long_lived_devices, short_lived_devices):
        series_lookup[long_lived_series]["devices"].append(l_device)
        series_lookup[short_lived_series]["devices"].append(s_device)

    return series_lookup

def get_nvidia_device():
    """
    Returns the device info (name and ID) for the NVIDIA device, if present.
    """
    pci_vga = ""

    try:
        lspci = subprocess.Popen(["lspci", "-nn"], stdout=subprocess.PIPE)
        pci_vga = subprocess.check_output(["grep", "-i", "VGA"], stdin=lspci.stdout)
    except subprocess.CalledProcessError:
        if __name__ == "__main__":
            print "Error: Problem retreiving VGA device info!"
        raise
    except OSError:
        if __name__ == "__main__":
            print "Error: Command 'lspci' not available!"
        raise

    if pci_vga != "":
        if "nvidia" in pci_vga.lower():
            pci_id_regex = re.compile('\:[0-9A-Fa-f]+\]')
            pci_id_match = pci_id_regex.search(pci_vga)
            id_start = pci_id_match.start() + 1
            id_end = pci_id_match.end() - 1
            pci_id = pci_vga[id_start:id_end].upper()

            device_name_regex = re.compile('nvidia.*\[10de')
            device_name_match = device_name_regex.search(pci_vga.lower())
            name_start = device_name_match.start()
            name_end = device_name_match.end() - 5
            device_name = pci_vga[name_start:name_end]

            return device(name=device_name, pci_id=pci_id)


    return None

def get_required_driver_series(device_id=None):
    """
    Returns the required driver series for the given or detected NVIDIA device.

    Keyword Args:
    device_id - The device PCI ID to check against the supported devices lists
    """
    if not device_id:
        device = get_nvidia_device()
        if device:
            device_id = device.pci_id

    if device_id:
        if not series_lookup:
            get_all_supported_devices()

        for driver_series, series_info in series_lookup.iteritems():
            if prefer_long_lived and driver_series in short_lived_version:
                continue
            elif not prefer_long_lived and driver_series in long_lived_version:
                continue

            for device in series_info["devices"]:
                if device_id == device.pci_id:
                    return driver_series

    return None

def get_latest_driver_version(device_id=None):
    """
    Returns the latest driver version of the required driver series for the
    given or detected NVIDIA device.

    Keyword Args:
    device_id - The device PCI ID to check against the supported devices lists
    """
    driver_series = get_required_driver_series(device_id)
    return series_lookup[driver_series]["latest_version"]

def __main():
    global verbose
    global prefer_long_lived
    latest = False
    series = True
    pci_id = None

    parser = argparse.ArgumentParser()
    parser.add_argument("--series", help="Output the required driver series for the detected NVIDIA device [Default]", action="store_true")
    parser.add_argument("--latest", help="Output the latest version number of the driver for the detected NVIDIA device", action="store_true")
    parser.add_argument("--longlived", help="Denotes that the long lived version of the current drivers should be prefered [Default]", action="store_true")
    parser.add_argument("--shortlived", help="Denotes that the short lived version of the current drivers should be prefered", action="store_true")
    parser.add_argument("--deviceid", help="Provide a device PCI ID to be used instead of auto-detecting one")
    parser.add_argument("-v", "--verbose", help="More detailed output", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        verbose = True

    if args.latest:
        latest = True
        series = False

    if args.shortlived:
        prefer_long_lived = False

    if args.deviceid:
        pci_id = args.deviceid.upper()
        if verbose:
            print "Device ID: " + pci_id
    else:
        if verbose:
            print "Searching for NVIDIA device..."
        device = get_nvidia_device()
        if device:
            if verbose:
                print "Device Found: " + device.name
                print "Device ID: " + device.pci_id
            pci_id = device.pci_id

    if pci_id:
        required_series = get_required_driver_series(pci_id)
        latest_version = None
        if required_series:
            latest_version = series_lookup[required_series]["latest_version"]

        if required_series:
            if verbose:
                series_designation = ""
                if required_series in long_lived_version or required_series in short_lived_version:
                    series_designation = "Current"
                else:
                    series_designation = "Legacy"

                print "Required " + series_designation  + " Driver Series: " + required_series + ".xx"
                print "Latest Driver Version: " + latest_version
            elif latest and latest_version:
                print latest_version
            elif series and required_series:
                print required_series
        elif verbose:
                print "No known compatible driver!"
    elif verbose:
            print "No NVIDIA device detected!"

if __name__ == "__main__":
    __main()
