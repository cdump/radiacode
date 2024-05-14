import unittest
import datetime
from radiacode.radiacode import RadiaCode
from radiacode.types import DoseRateDB, Event, RareData, RawData, RealTimeData, Spectrum

class TestRadiaCodeIntegration(unittest.TestCase):
    """ 
    This test class requires a real and available Radiacode
    """
    @classmethod
    def setUpClass(cls):
        # Connect to the device only once
        cls.rc = RadiaCode(bluetooth_serial='RadiaCode-10')

    def test_serial_number_integration(self):
        serial_number = self.rc.serial_number()
        
        self.assertIsInstance(serial_number, str)
        self.assertIn('RC-10', serial_number)

    def test_fw_version_integration(self):
        fw_version = self.rc.fw_version()
        
        self.assertIsInstance(fw_version, tuple)
        self.assertEqual(len(fw_version), 2)

        # tuple[tuple[int, int, str], tuple[int, int, str]]:
        for ver in fw_version:
            self.assertIsInstance(ver, tuple)
            self.assertEqual(len(ver), 3)
            self.assertIsInstance(ver[0], int)
            self.assertIsInstance(ver[1], int)
            self.assertIsInstance(ver[2], str)

    def test_spectrum_integration(self):
        spectrum = self.rc.spectrum()
        
        self.assertIsInstance(spectrum, Spectrum)
        self.assertIsInstance(spectrum.duration, datetime.timedelta)
        self.assertIsInstance(spectrum.a0, float)
        self.assertIsInstance(spectrum.a1, float)
        self.assertIsInstance(spectrum.a2, float)
        self.assertIsInstance(spectrum.counts, list)
        self.assertTrue(all(isinstance(count, int) for count in spectrum.counts))

    def test_data_buf_integration(self):
        data_buf = self.rc.data_buf()
        
        self.assertIsInstance(data_buf, list)
        for item in data_buf:
            self.assertTrue(isinstance(item, (DoseRateDB, RareData, RealTimeData, RawData, Event)))
            self.assertIsInstance(item.dt, datetime.datetime)

    def test_spectrum_accum_integration(self):
        spectrum_accum = self.rc.spectrum_accum()
        
        self.assertIsInstance(spectrum_accum, Spectrum)
        self.assertIsInstance(spectrum_accum.duration, datetime.timedelta)
        self.assertIsInstance(spectrum_accum.a0, float)
        self.assertIsInstance(spectrum_accum.a1, float)
        self.assertIsInstance(spectrum_accum.a2, float)
        self.assertIsInstance(spectrum_accum.counts, list)
        self.assertTrue(all(isinstance(count, int) for count in spectrum_accum.counts))

    def test_configuration_integration(self):
        configuration = self.rc.configuration()
        
        self.assertIsInstance(configuration, str)
        self.assertIn('DeviceParams', configuration)
        self.assertIn('CHN_ChargeLevel', configuration)

    def test_hw_serial_number_integration(self):
        hw_serial_number = self.rc.hw_serial_number()
        
        # Format is: XXXXXXXX-XXXXXXXX-XXXXXXXX (hex)
        self.assertIsInstance(hw_serial_number, str)
        self.assertIn('-', hw_serial_number)

    def test_status_integration(self):
        status = self.rc.status()
        
        self.assertIsInstance(status, str)
        self.assertIn('flags: ', status)

    def test_commands_integration(self):
        commands = self.rc.commands()

        self.assertIsInstance(commands, str)
        self.assertIn('VSFR_DEVICE_CTRL', commands)
        self.assertIn('VSFR_SYS_MCU_TEMP', commands)

if __name__ == '__main__':
    unittest.main()
