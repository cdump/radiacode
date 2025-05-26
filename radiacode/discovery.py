#!/usr/bin/env python3
"""
RadiaCode device discovery utilities
"""
import time
import typing
from bluepy.btle import Scanner, DefaultDelegate, BTLEException


class ScanDelegate(DefaultDelegate):
    """Delegate to handle BLE scan results"""
    def __init__(self):
        DefaultDelegate.__init__(self)


def discover_radiacode_devices(timeout: float = 5.0) -> typing.List[typing.Tuple[str, str]]:
    """
    Scan for RadiaCode devices via Bluetooth LE
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        List of tuples (mac_address, device_name)
    """
    devices = []
    
    try:
        scanner = Scanner().withDelegate(ScanDelegate())
        entries = scanner.scan(timeout)
        
        for entry in entries:
            name = None
            # Check for device name in scan data
            for (adtype, desc, value) in entry.getScanData():
                if desc == "Complete Local Name":
                    name = value
                    break
            
            # RadiaCode devices typically have names starting with "RadiaCode" or "RC-"
            if name and ("RadiaCode" in name or name.startswith("RC-")):
                devices.append((entry.addr, name))
                
    except BTLEException as e:
        # If scanning fails (e.g., no permissions), return empty list
        import os
        error_msg = str(e)
        
        if "Permission denied" in error_msg or "Operation not permitted" in error_msg:
            if os.geteuid() != 0:
                print(f"⚠️  Bluetooth scanning failed: {e}")
                print("\nThis is likely a permission issue. Try:")
                print("  1. Run with sudo")
                print("  2. Add your user to the bluetooth group:")
                print(f"     sudo usermod -a -G bluetooth {os.environ.get('USER', '$USER')}")
                print("     Then logout and login again")
            else:
                print(f"Bluetooth scanning failed: {e}")
        else:
            print(f"Bluetooth scanning failed: {e}")
            if "No such device" in error_msg:
                print("  - Check that Bluetooth is enabled")
                print("  - Verify Bluetooth adapter is present")
        
    return devices


def find_first_radiacode(timeout: float = 5.0) -> typing.Optional[str]:
    """
    Find the first available RadiaCode device
    
    Args:
        timeout: Scan timeout in seconds
        
    Returns:
        MAC address of first device found, or None
    """
    devices = discover_radiacode_devices(timeout)
    if devices:
        mac, name = devices[0]
        print(f"Found RadiaCode device: {name} ({mac})")
        return mac
    return None


def list_all_radiacode_devices(timeout: float = 10.0) -> None:
    """
    List all RadiaCode devices found
    
    Args:
        timeout: Scan timeout in seconds
    """
    print(f"Scanning for RadiaCode devices ({timeout}s)...")
    devices = discover_radiacode_devices(timeout)
    
    if not devices:
        print("No RadiaCode devices found.")
        print("\nTroubleshooting:")
        print("1. Ensure device is powered on")
        print("2. Check Bluetooth is enabled on device") 
        print("3. Disconnect from phone app if connected")
        print("4. Try running with sudo")
    else:
        print(f"\nFound {len(devices)} RadiaCode device(s):")
        for i, (mac, name) in enumerate(devices, 1):
            print(f"  {i}. {name} - {mac}")


if __name__ == "__main__":
    # Test discovery when run directly
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_all_radiacode_devices()
    else:
        mac = find_first_radiacode()
        if mac:
            print(f"First device MAC: {mac}")
        else:
            print("No devices found")