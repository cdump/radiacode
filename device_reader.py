#!/usr/bin/env python3
"""
Standalone RadiaCode device reader
Publishes data to a JSON file that the webserver can read
"""
import asyncio
import json
import argparse
import signal
import time
from pathlib import Path
from datetime import datetime, timezone
from collections import deque

class DeviceReader:
    def __init__(self, output_path="/tmp/radiacode_data.json", mock=False):
        self.output_path = Path(output_path)
        self.mock = mock
        self.running = True
        self.device = None
        self.data_buffer = deque(maxlen=300)  # 5 minutes at 1Hz
        self.last_spectrum_time = 0
        self.spectrum_interval = 30  # Update spectrum every 30s
        
    async def connect(self, bluetooth_mac=None):
        """Connect to device with retry logic"""
        retry_count = 0
        while self.running and retry_count < 3:
            try:
                if self.mock:
                    print("Using mock device")
                    from radiacode_examples.mock_data_generator import MockRadiaCode
                    self.device = MockRadiaCode()
                    return True
                
                from radiacode import RadiaCode
                if bluetooth_mac:
                    print(f"Connecting to Bluetooth {bluetooth_mac}...")
                    self.device = RadiaCode(bluetooth_mac=bluetooth_mac)
                else:
                    print("Connecting via USB...")
                    self.device = RadiaCode()
                
                serial = self.device.serial_number()
                print(f"✓ Connected to {serial}")
                return True
                
            except Exception as e:
                retry_count += 1
                print(f"Connection attempt {retry_count} failed: {e}")
                if retry_count < 3:
                    await asyncio.sleep(5)
        
        return False
    
    async def read_loop(self):
        """Main reading loop"""
        while self.running:
            try:
                # Read real-time data
                data_points = []
                for data in self.device.data_buf():
                    if not self.running:
                        break
                    # Only process RealTimeData or DoseRateDB objects
                    if hasattr(data, 'count_rate'):
                        data_point = {
                            'timestamp': data.dt.isoformat(),
                            'count_rate': data.count_rate,
                            'dose_rate': data.dose_rate,
                        }
                        # Add optional fields if they exist
                        if hasattr(data, 'count_rate_err'):
                            data_point['count_rate_err'] = data.count_rate_err
                        if hasattr(data, 'dose_rate_err'):
                            data_point['dose_rate_err'] = data.dose_rate_err
                        
                        data_points.append(data_point)
                        self.data_buffer.append(data_points[-1])
                
                # Get spectrum periodically
                spectrum_data = None
                now = time.time()
                if now - self.last_spectrum_time > self.spectrum_interval:
                    spectrum = self.device.spectrum()
                    spectrum_accum = self.device.spectrum_accum()
                    spectrum_data = {
                        'current': {
                            'duration': spectrum.duration.total_seconds(),
                            'coefficients': [spectrum.a0, spectrum.a1, spectrum.a2],
                            'counts': spectrum.counts[:100]  # First 100 for preview
                        },
                        'accumulated': {
                            'duration': spectrum_accum.duration.total_seconds(),
                            'coefficients': [spectrum_accum.a0, spectrum_accum.a1, spectrum_accum.a2],
                            'counts': spectrum_accum.counts
                        }
                    }
                    self.last_spectrum_time = now
                
                # Write to file atomically
                output = {
                    'device': {
                        'connected': True,
                        'serial': getattr(self.device, 'serial_number', lambda: 'mock')(),
                        'last_update': datetime.now(timezone.utc).isoformat()
                    },
                    'realtime': {
                        'latest': data_points[-1] if data_points else None,
                        'buffer': list(self.data_buffer)
                    },
                    'spectrum': spectrum_data
                }
                
                # Atomic write
                temp_path = self.output_path.with_suffix('.tmp')
                with open(temp_path, 'w') as f:
                    json.dump(output, f)
                temp_path.replace(self.output_path)
                
                print(f"✓ Updated {len(data_points)} readings, "
                      f"latest: {data_points[-1]['count_rate']:.1f} CPS" if data_points else "No new data")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"Read error: {e}")
                # Write disconnected state
                error_output = {
                    'device': {
                        'connected': False,
                        'error': str(e),
                        'last_update': datetime.now(timezone.utc).isoformat()
                    }
                }
                with open(self.output_path, 'w') as f:
                    json.dump(error_output, f)
                
                await asyncio.sleep(5)  # Wait before retry
    
    async def run(self, bluetooth_mac=None):
        """Main run method"""
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.shutdown)
        
        # Connect
        if not await self.connect(bluetooth_mac):
            print("Failed to connect to device")
            return
        
        # Run read loop
        try:
            await self.read_loop()
        finally:
            if self.device and hasattr(self.device._connection, 'close'):
                self.device._connection.close()
            print("Device reader stopped")
    
    def shutdown(self):
        """Graceful shutdown"""
        print("\nShutting down...")
        self.running = False

async def main():
    parser = argparse.ArgumentParser(description='RadiaCode device reader service')
    parser.add_argument('--bluetooth-mac', '-b', help='Bluetooth MAC address (auto-discover if not specified)')
    parser.add_argument('--output', '-o', default='/tmp/radiacode_data.json', 
                       help='Output JSON file path')
    parser.add_argument('--mock', action='store_true', help='Use mock device')
    parser.add_argument('--list', action='store_true', help='List available devices and exit')
    args = parser.parse_args()
    
    # Handle device listing
    if args.list:
        from radiacode.discovery import list_all_radiacode_devices
        list_all_radiacode_devices()
        return
    
    # Auto-discover if no MAC specified and not using mock
    bluetooth_mac = args.bluetooth_mac
    if not bluetooth_mac and not args.mock:
        print("No MAC address specified, scanning for RadiaCode devices...")
        
        # Check permissions before scanning
        import os
        import grp
        import sys
        
        if os.geteuid() != 0:
            try:
                bluetooth_gid = grp.getgrnam('bluetooth').gr_gid
                user_groups = os.getgroups()
                if bluetooth_gid not in user_groups:
                    print("\n⚠️  Permission issue detected:")
                    print("  You are not in the 'bluetooth' group")
                    print("\n  To fix this permanently:")
                    print(f"    sudo usermod -a -G bluetooth {os.getlogin()}")
                    print("    Then logout and login again")
                    print("\n  Or run with sudo:")
                    print(f"    sudo {' '.join(sys.argv)}")
                    return
            except KeyError:
                # bluetooth group doesn't exist
                print("\n⚠️  Bluetooth access requires root privileges")
                print(f"  Run with: sudo {' '.join(sys.argv)}")
                return
            except OSError:
                # getlogin() can fail in some environments
                pass
        
        from radiacode.discovery import find_first_radiacode
        bluetooth_mac = find_first_radiacode()
        if not bluetooth_mac:
            print("No RadiaCode devices found. Specify MAC address or use --mock")
            return
    
    reader = DeviceReader(output_path=args.output, mock=args.mock)
    await reader.run(bluetooth_mac)

if __name__ == "__main__":
    # Check if we need to restart with sudo for discovery
    import os
    import sys
    import grp
    
    if '--list' in sys.argv and os.geteuid() != 0:
        # Check if user is in bluetooth group
        try:
            bluetooth_gid = grp.getgrnam('bluetooth').gr_gid
            user_groups = os.getgroups()
            if bluetooth_gid not in user_groups:
                print("⚠️  Permission issue: You are not in the 'bluetooth' group")
                print("\nTo fix this permanently:")
                print(f"  sudo usermod -a -G bluetooth {os.getlogin()}")
                print("  Then logout and login again")
                print("\nOr run with sudo:")
                print(f"  sudo {' '.join(sys.argv)}")
            else:
                print("Note: Bluetooth scanning may require root privileges.")
                print(f"If scanning fails, try: sudo {' '.join(sys.argv)}")
        except KeyError:
            print("Note: Bluetooth scanning requires root privileges.")
            print(f"Please run with: sudo {' '.join(sys.argv)}")
        except OSError:
            print("Note: Bluetooth scanning requires root privileges.")
            print(f"Please run with: sudo {' '.join(sys.argv)}")
        sys.exit(1)
    
    asyncio.run(main())