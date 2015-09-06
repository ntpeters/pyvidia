#!/usr/bin/env python

# Pyvidia
# Gets the required driver series for the detected NVIDIA device.
# Also able to get the latest version of the required driver series.
# Parses the list of supported devices for each driver version from the NVIDIA site.

from __future__ import absolute_import
from __future__ import print_function
import argparse
import collections
import platform
import re
import subprocess
import sys
from bs4 import BeautifulSoup
from bs4 import NavigableString
import six
from six.moves import zip

# Get proper urllib for Python version
try:
    # Python 3
    import urllib.request as urllib2
except:
    # Python 2
    import urllib2

# URL to scrape device info from for legacy devices
legacy_device_url = "http://www.nvidia.com/object/IO_32667.html"
# URL to scrape version number info from
unix_driver_url = "http://www.nvidia.com/object/unix.html"
# URLs to scrape device info from for the long and short lived drivers
long_lived_url = ""
short_lived_url = ""
# Versions of the long and short lived current drivers
long_lived_version = ""
short_lived_version = ""
# Versions of the legacy drivers
legacy_versions = []
# Download links for each version
version_urls = {}

# Whether this OS is 64-bit or not
is_64bit = False

# Named tuple representing a device, containing its name and PCI ID
device = collections.namedtuple("Device", ["name", "pci_id"])

# Dictionary keyed by driver series, containing a dictionary with the
# latest version number and a list of supported devices.
# For Example:
#     { <driver-series> :
#       { latest_version : <latest-version>,
#         devices : [ device( name : <device-name>, pci_id : <device-pci-id> ) ],
#         url : <download-url>
#       }
#     }
series_lookup = None

# Whether verbose mode should be enabled or not
verbose = False
# Denotes if the long lived current driver should be preferred over the short lived
prefer_long_lived = True

# Define the default parser for BS4 to use
parser = "lxml"

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
    soup = BeautifulSoup(legacy_device_page, parser)

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
    soup = BeautifulSoup(page, parser)

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

def __get_download_url_for_tag(tag):
    if not tag: return None

    dl_page_link = tag['href']
    if not dl_page_link: return None
    if dl_page_link[0] == "/":
        dl_page_link = "http://www.nvidia.com" + dl_page_link

    dl_page = urllib2.urlopen(dl_page_link)
    dl_soup = BeautifulSoup(dl_page, parser)

    eula_page_link = dl_soup.find('img', alt='Download')
    if eula_page_link is None:
        eula_page_link = dl_soup.find('img', alt='download')
    if not eula_page_link: return None
    eula_page_link = eula_page_link.parent['href']
    if eula_page_link[0] == "/":
        eula_page_link = "http://www.nvidia.com" + eula_page_link

    eula_page = urllib2.urlopen(eula_page_link)
    eula_soup = BeautifulSoup(eula_page, parser)

    download_link = eula_soup.find('img', alt='Agree & Download').parent['href']

    return download_link

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
    soup = BeautifulSoup(page, parser)

    driver_section = None

    p_tags = soup.find_all('p')
    for p_tag in p_tags:
        section_header = p_tag.find('strong')
        target_system =  "Linux x86_64/" if is_64bit else "Linux x86/"
        if section_header and target_system in section_header.text:
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
                download_url = __get_download_url_for_tag(child)

                this_version = None
                if long_lived_found and long_lived_version == "":
                    long_lived_version = child.text
                    this_version = child.text
                elif short_lived_found and short_lived_version == "":
                    short_lived_version = child.text
                    this_version = child.text
                elif legacy_found:
                    legacy_versions.append(child.text)
                    legacy_found = False
                    this_version = child.text

                if this_version:
                    version_urls[this_version] = download_url

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

            try:

                series_lookup[series]["url"]
            except KeyError:
                series_lookup[series]["url"] = version_urls[latest_version]
                pass

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

    series_lookup[long_lived_series]["url"] = version_urls[long_lived_version]
    series_lookup[short_lived_series]["url"] = version_urls[short_lived_version]

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
            print("Error: Problem retreiving VGA device info!")
        raise
    except OSError:
        if __name__ == "__main__":
            print("Error: Command 'lspci' not available!")
        raise

    if pci_vga != "":
        if "nvidia" in pci_vga.lower().decode('utf-8'):
            pci_id_regex = re.compile('\:[0-9A-Fa-f]+\]')
            pci_id_match = pci_id_regex.search(pci_vga.decode('utf-8'))
            id_start = pci_id_match.start() + 1
            id_end = pci_id_match.end() - 1
            pci_id = pci_vga[id_start:id_end].upper()

            device_name_regex = re.compile('nvidia.*\[10de')
            device_name_match = device_name_regex.search(pci_vga.lower().decode('utf-8'))
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

        for driver_series, series_info in six.iteritems(series_lookup):
            if prefer_long_lived and driver_series in short_lived_version:
                continue
            elif not prefer_long_lived and driver_series in long_lived_version:
                continue

            for device in series_info["devices"]:
                if device_id.decode('utf-8') == device.pci_id:
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

def get_driver_url(device_id=None):
    """
    Returns the download URL of the required driver for the given or detected
    device.

    Keyward Args:
    device_id - The device PCI ID to check against the supported devices lists
    """
    pci_id = device_id
    if not pci_id:
        device = get_nvidia_device()
        pci_id = device.pci_id

    if pci_id:
        required_series = get_required_driver_series(pci_id)

    if series_lookup:
        return series_lookup[required_series]["url"]

    return None

def __main():
    global verbose
    global prefer_long_lived
    global is_64bit

    if "Linux" not in platform.system():
        raise RuntimeError("[" + platform.system() + " Unsupported] - Pyvidia only support Linux systems!")

    is_64bit = platform.machine().endswith("64")

    latest = False
    series = True
    pci_id = None

    parser = argparse.ArgumentParser()
    parser.add_argument("--series", help="Output the required driver series for the detected NVIDIA device [Default]", action="store_true")
    parser.add_argument("--latest", help="Output the latest version number of the driver for the detected NVIDIA device", action="store_true")
    parser.add_argument("--longlived", help="Denotes that the long lived version of the current drivers should be prefered [Default]", action="store_true")
    parser.add_argument("--shortlived", help="Denotes that the short lived version of the current drivers should be prefered", action="store_true")
    parser.add_argument("--deviceid", help="Provide a device PCI ID to be used instead of auto-detecting one")
    parser.add_argument("--url", help="Output the download URL for the required driver", action="store_true")
    parser.add_argument("-v", "--verbose", help="More detailed output", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        verbose = True

    if args.latest:
        latest = True
        series = False

    if args.shortlived:
        prefer_long_lived = False

    if verbose:
        print("OS: " + platform.system() + " " + platform.machine())

    if args.deviceid:
        pci_id = args.deviceid.upper().encode('utf-8')
        if verbose:
            print("Device ID: " + pci_id)
    else:
        if verbose:
            print("Searching for NVIDIA device...")
        device = get_nvidia_device()
        if device:
            if verbose:
                print("Device Found: " + device.name.decode('utf-8'))
                print("Device ID: " + device.pci_id.decode('utf-8'))
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

                print("Required " + series_designation  + " Driver Series: " + required_series + ".xx")
                print("Latest Driver Version: " + latest_version)
                print("Download URL: " + series_lookup[required_series]["url"])
            elif args.url:
                print(series_lookup[required_series]["url"])
            elif latest and latest_version:
                print(latest_version)
            elif series and required_series:
                print(required_series)
        elif verbose:
                print("No known compatible driver!")
    elif verbose:
            print("No NVIDIA device detected!")

if __name__ == "__main__":
    __main()
