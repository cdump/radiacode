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
from enum import Enum
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"

class DeviceReader:
    def __init__(self, output_path="/tmp/radiacode_data.json", mock=False):
        self.output_path = Path(output_path)
        self.mock = mock
        self.running = True
        self.device = None
        self.data_buffer = deque(maxlen=300)  # 5 minutes at 1Hz
        self.last_spectrum_time = 0
        self.spectrum_interval = 30  # Update spectrum every 30s
        
        # Connection state tracking
        self.connection_state = ConnectionState.DISCONNECTED
        self.bluetooth_mac = None
        self.device_serial = None
        
        # Reconnection parameters
        self.reconnect_delay = 1.0  # Start with 1 second
        self.max_reconnect_delay = 60.0  # Max 60 seconds
        self.reconnect_backoff_factor = 2.0
        
    def _set_connection_state(self, state: ConnectionState):
        """Update connection state and log changes"""
        if self.connection_state != state:
            logger.info(f"Connection state: {self.connection_state.value} → {state.value}")
            self.connection_state = state
    
    async def connect(self, bluetooth_mac=None):
        """Connect to device"""
        self._set_connection_state(ConnectionState.CONNECTING)
        self.bluetooth_mac = bluetooth_mac
        
        try:
            if self.mock:
                logger.info("Using mock device")
                from radiacode_examples.mock_data_generator import MockRadiaCode
                self.device = MockRadiaCode()
                self.device_serial = "RC-MOCK-000001"
            else:
                from radiacode import RadiaCode
                if bluetooth_mac:
                    logger.info(f"Connecting to Bluetooth {bluetooth_mac}...")
                    self.device = RadiaCode(bluetooth_mac=bluetooth_mac)
                else:
                    logger.info("Connecting via USB...")
                    self.device = RadiaCode()
                
                self.device_serial = self.device.serial_number()
            
            self._set_connection_state(ConnectionState.CONNECTED)
            logger.info(f"✓ Connected to {self.device_serial}")
            
            # Reset reconnect delay on successful connection
            self.reconnect_delay = 1.0
            return True
            
        except Exception as e:
            self._set_connection_state(ConnectionState.DISCONNECTED)
            logger.error(f"Connection failed: {e}")
            return False
    
    async def reconnect(self):
        """Attempt to reconnect with exponential backoff"""
        self._set_connection_state(ConnectionState.RECONNECTING)
        
        while self.running and self.connection_state != ConnectionState.CONNECTED:
            logger.info(f"Reconnection attempt in {self.reconnect_delay:.1f} seconds...")
            await asyncio.sleep(self.reconnect_delay)
            
            if not self.running:
                break
                
            if await self.connect(self.bluetooth_mac):
                return True
            
            # Exponential backoff
            self.reconnect_delay = min(
                self.reconnect_delay * self.reconnect_backoff_factor,
                self.max_reconnect_delay
            )
        
        return False
    
    async def read_loop(self):
        """Main reading loop with automatic reconnection"""
        while self.running:
            if self.connection_state != ConnectionState.CONNECTED:
                # Try to reconnect
                if not await self.reconnect():
                    break
                continue
            
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
                        'serial': self.device_serial,
                        'last_update': datetime.now(timezone.utc).isoformat(),
                        'connection_state': self.connection_state.value
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
                
                if data_points:
                    logger.debug(f"Updated {len(data_points)} readings, "
                                f"latest: {data_points[-1]['count_rate']:.1f} CPS")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                # Check for specific Bluetooth disconnect error
                error_msg = str(e)
                if "BTLEDisconnectError" in str(type(e)) or "disconnected" in error_msg.lower():
                    logger.error("Bluetooth connection lost")
                else:
                    logger.error(f"Read error: {e}")
                
                self._set_connection_state(ConnectionState.DISCONNECTED)
                
                # Close existing connection
                try:
                    if self.device and hasattr(self.device._connection, 'close'):
                        self.device._connection.close()
                except:
                    pass
                self.device = None
                
                # Write disconnected state
                error_output = {
                    'device': {
                        'connected': False,
                        'error': str(e),
                        'last_update': datetime.now(timezone.utc).isoformat(),
                        'connection_state': self.connection_state.value,
                        'reconnect_delay': self.reconnect_delay
                    }
                }
                with open(self.output_path, 'w') as f:
                    json.dump(error_output, f)
    
    async def run(self, bluetooth_mac=None):
        """Main run method"""
        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.shutdown)
        
        # Initial connection attempt
        if not await self.connect(bluetooth_mac):
            logger.warning("Initial connection failed, will keep trying...")
        
        # Run read loop (handles reconnection)
        try:
            await self.read_loop()
        finally:
            if self.device and hasattr(self.device._connection, 'close'):
                self.device._connection.close()
            logger.info("Device reader stopped")
    
    def shutdown(self):
        """Graceful shutdown"""
        logger.info("Shutting down...")
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