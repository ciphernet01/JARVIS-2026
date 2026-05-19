import unittest
from unittest.mock import MagicMock, patch
from modules.services.system_manager import SystemManager

class TestSystemManager(unittest.TestCase):
    def setUp(self):
        # Mock Windows specific imports that might fail on non-Windows/CI environments
        self.patcher_wmi = patch('wmi.WMI')
        self.patcher_com = patch('comtypes.CoInitialize')
        self.patcher_com_un = patch('comtypes.CoUninitialize')
        
        self.mock_wmi = self.patcher_wmi.start()
        self.patcher_com.start()
        self.patcher_com_un.start()
        
        self.manager = SystemManager()

    def tearDown(self):
        self.patcher_wmi.stop()
        self.patcher_com.stop()
        self.patcher_com_un.stop()

    @patch('modules.services.system_manager.psutil.sensors_battery')
    def test_get_power_status(self, mock_battery):
        mock_battery.return_value = MagicMock(percent=85, power_plugged=True, secsleft=3600)
        status = self.manager.get_power_status()
        self.assertEqual(status['status'], 'success')
        self.assertEqual(status['percent'], 85)
        self.assertTrue(status['power_plugged'])

    @patch('modules.services.system_manager.sbc.get_brightness')
    def test_get_brightness(self, mock_get_b):
        mock_get_b.return_value = [75]
        status = self.manager.get_brightness()
        self.assertEqual(status['status'], 'success')
        self.assertEqual(status['brightness'], 75)

    @patch('modules.services.system_manager.psutil.cpu_percent')
    @patch('modules.services.system_manager.psutil.virtual_memory')
    def test_get_system_load(self, mock_mem, mock_cpu):
        mock_cpu.return_value = 15.5
        mock_mem.return_value = MagicMock(percent=45.0)
        load = self.manager.get_system_load()
        self.assertEqual(load['cpu_percent'], 15.5)
        self.assertEqual(load['memory_percent'], 45.0)

    def test_capability_matrix(self):
        capabilities = self.manager.capability_matrix()
        self.assertIn('os', capabilities)
        self.assertIn('features', capabilities)

if __name__ == '__main__':
    unittest.main()
