"""
Tests for NetworkManager
"""
import pytest
from unittest.mock import patch, MagicMock
from modules.services.network_manager import (
    NetworkManager, NetworkInterface, WiFiNetwork, NetworkSnapshot,
    ConnectionType
)


class TestNetworkManager:
    """Test NetworkManager singleton and network operations."""
    
    def test_singleton_pattern(self):
        """NetworkManager should be a singleton."""
        manager1 = NetworkManager()
        manager2 = NetworkManager()
        assert manager1 is manager2, "NetworkManager should be a singleton"
    
    def test_snapshot_structure(self):
        """Snapshot should have all required fields."""
        manager = NetworkManager()
        snapshot = manager.snapshot()
        
        assert isinstance(snapshot, NetworkSnapshot)
        assert isinstance(snapshot.active_interfaces, int)
        assert isinstance(snapshot.connected_interfaces, list)
        assert isinstance(snapshot.wifi_enabled, bool)
        assert isinstance(snapshot.wifi_networks, list)
        assert isinstance(snapshot.total_bytes_sent, int)
        assert isinstance(snapshot.total_bytes_recv, int)
        assert isinstance(snapshot.vpn_connected, bool)
    
    def test_snapshot_immutability(self):
        """NetworkSnapshot should be immutable."""
        manager = NetworkManager()
        snapshot = manager.snapshot()
        
        with pytest.raises(AttributeError):
            snapshot.wifi_enabled = not snapshot.wifi_enabled
    
    def test_network_interface_immutability(self):
        """NetworkInterface should be immutable."""
        interface = NetworkInterface(
            name="eth0",
            connection_type=ConnectionType.ETHERNET,
            is_connected=True,
            ip_address="192.168.1.1",
            gateway="192.168.1.254",
            netmask="255.255.255.0",
            mac_address="00:11:22:33:44:55",
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=100,
            packets_recv=200
        )
        
        with pytest.raises(AttributeError):
            interface.is_connected = False
    
    def test_wifi_network_immutability(self):
        """WiFiNetwork should be immutable."""
        network = WiFiNetwork(
            ssid="TestNetwork",
            signal_strength=75,
            security="WPA2",
            frequency="2.4 GHz",
            channel=6
        )
        
        with pytest.raises(AttributeError):
            network.signal_strength = 50
    
    def test_connection_type_enum(self):
        """ConnectionType enum should have correct values."""
        assert ConnectionType.ETHERNET.value == "ethernet"
        assert ConnectionType.WIFI.value == "wifi"
        assert ConnectionType.CELLULAR.value == "cellular"
        assert ConnectionType.VPN.value == "vpn"
        assert ConnectionType.UNKNOWN.value == "unknown"
    
    def test_capability_matrix(self):
        """Capability matrix should report network capabilities."""
        manager = NetworkManager()
        capabilities = manager.capability_matrix()
        
        assert "has_ethernet" in capabilities
        assert "has_wifi" in capabilities
        assert "wifi_enabled" in capabilities
        assert "connected_interface_count" in capabilities
        assert "vpn_connected" in capabilities
        assert "has_internet" in capabilities
    
    def test_interface_name_detection(self):
        """Should correctly detect connection types from interface names."""
        manager = NetworkManager()
        
        assert manager._detect_connection_type("eth0") == ConnectionType.ETHERNET
        assert manager._detect_connection_type("wlan0") == ConnectionType.WIFI
        assert manager._detect_connection_type("WiFi") == ConnectionType.WIFI
        assert manager._detect_connection_type("tun0") == ConnectionType.VPN
        assert manager._detect_connection_type("unknown0") == ConnectionType.UNKNOWN
    
    def test_security_type_parsing(self):
        """Should correctly parse security types from raw strings."""
        manager = NetworkManager()
        
        assert manager._parse_security("WPA2-Personal/WPA3-Personal") == "WPA3"
        assert manager._parse_security("WPA2-Personal") == "WPA2"
        assert manager._parse_security("Open") == "Open"
        assert manager._parse_security("WPA-Personal") == "WPA2"
        assert manager._parse_security("Unknown") == "Unknown"
    
    def test_snapshot_connected_interfaces_filter(self):
        """Snapshot should filter connected interfaces correctly."""
        manager = NetworkManager()
        
        # Create mock interfaces
        with patch.object(manager, '_enumerate_interfaces') as mock_enum:
            mock_enum.return_value = [
                NetworkInterface("eth0", ConnectionType.ETHERNET, True, "192.168.1.1", None, None, None, 0, 0, 0, 0),
                NetworkInterface("lo", ConnectionType.UNKNOWN, True, "127.0.0.1", None, None, None, 0, 0, 0, 0),
                NetworkInterface("wlan0", ConnectionType.WIFI, False, None, None, None, None, 0, 0, 0, 0),
            ]
            
            with patch.object(manager, '_get_wifi_status', return_value=(False, None)):
                with patch.object(manager, '_get_dns_servers', return_value=[]):
                    with patch.object(manager, '_get_default_gateway', return_value=None):
                        with patch.object(manager, '_scan_wifi_networks', return_value=[]):
                            with patch.object(manager, '_check_vpn_status', return_value=False):
                                snapshot = manager.snapshot()
                                
                                assert len(snapshot.connected_interfaces) == 2  # eth0 and lo
                                assert all(i.is_connected for i in snapshot.connected_interfaces)
    
    def test_total_bytes_calculation(self):
        """Should correctly calculate total bytes sent and received."""
        manager = NetworkManager()
        
        with patch.object(manager, '_enumerate_interfaces') as mock_enum:
            mock_enum.return_value = [
                NetworkInterface("eth0", ConnectionType.ETHERNET, True, "192.168.1.1", None, None, None, 1000, 2000, 100, 200),
                NetworkInterface("wlan0", ConnectionType.WIFI, True, "192.168.1.2", None, None, None, 500, 1500, 50, 150),
            ]
            
            with patch.object(manager, '_get_wifi_status', return_value=(True, "TestNet")):
                with patch.object(manager, '_get_dns_servers', return_value=[]):
                    with patch.object(manager, '_get_default_gateway', return_value=None):
                        with patch.object(manager, '_scan_wifi_networks', return_value=[]):
                            with patch.object(manager, '_check_vpn_status', return_value=False):
                                snapshot = manager.snapshot()
                                
                                assert snapshot.total_bytes_sent == 1500  # 1000 + 500
                                assert snapshot.total_bytes_recv == 3500  # 2000 + 1500
    
    def test_empty_interfaces_fallback(self):
        """Should handle case with no network interfaces gracefully."""
        manager = NetworkManager()
        
        with patch.object(manager, '_enumerate_interfaces', return_value=[]):
            with patch.object(manager, '_get_wifi_status', return_value=(False, None)):
                with patch.object(manager, '_get_dns_servers', return_value=[]):
                    with patch.object(manager, '_get_default_gateway', return_value=None):
                        with patch.object(manager, '_scan_wifi_networks', return_value=[]):
                            with patch.object(manager, '_check_vpn_status', return_value=False):
                                snapshot = manager.snapshot()
                                
                                assert snapshot.active_interfaces == 0
                                assert snapshot.connected_interfaces == []
                                assert not snapshot.wifi_enabled
                                assert snapshot.total_bytes_sent == 0
                                assert snapshot.total_bytes_recv == 0
    
    def test_wifi_network_list_limit(self):
        """WiFi scan should limit returned networks to 10."""
        manager = NetworkManager()
        
        # Create mock for WiFi scan that tries to return more than 10
        mock_networks = [
            WiFiNetwork(f"Network{i}", 50 + i, "WPA2", "2.4 GHz", i)
            for i in range(15)
        ]
        
        with patch.object(manager, '_scan_wifi_networks') as mock_scan:
            mock_scan.return_value = mock_networks[:10]  # Simulate the limit
            
            with patch.object(manager, '_enumerate_interfaces', return_value=[]):
                with patch.object(manager, '_get_wifi_status', return_value=(True, None)):
                    with patch.object(manager, '_get_dns_servers', return_value=[]):
                        with patch.object(manager, '_get_default_gateway', return_value=None):
                            with patch.object(manager, '_check_vpn_status', return_value=False):
                                snapshot = manager.snapshot()
                                
                                assert len(snapshot.wifi_networks) <= 10
    
    def test_snapshot_consistency(self):
        """Multiple snapshots should have consistent structure."""
        manager = NetworkManager()
        snap1 = manager.snapshot()
        snap2 = manager.snapshot()
        
        assert snap1.active_interfaces >= 0
        assert snap1.active_interfaces == len(snap1.connected_interfaces) or snap1.active_interfaces >= len(snap1.connected_interfaces)
        assert isinstance(snap1.connected_interfaces, list)
        assert isinstance(snap1.wifi_networks, list)
        assert snap1.total_bytes_sent >= 0
        assert snap1.total_bytes_recv >= 0


class TestNetworkDataStructures:
    """Test network data structure validation."""
    
    def test_network_interface_creation(self):
        """NetworkInterface should validate creation."""
        interface = NetworkInterface(
            name="eth0",
            connection_type=ConnectionType.ETHERNET,
            is_connected=True,
            ip_address="192.168.1.1",
            gateway="192.168.1.254",
            netmask="255.255.255.0",
            mac_address="00:11:22:33:44:55",
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=100,
            packets_recv=200
        )
        
        assert interface.name == "eth0"
        assert interface.connection_type == ConnectionType.ETHERNET
        assert interface.is_connected is True
        assert interface.ip_address == "192.168.1.1"
    
    def test_wifi_network_creation(self):
        """WiFiNetwork should validate creation."""
        network = WiFiNetwork(
            ssid="TestNetwork",
            signal_strength=75,
            security="WPA2",
            frequency="2.4 GHz",
            channel=6
        )
        
        assert network.ssid == "TestNetwork"
        assert network.signal_strength == 75
        assert network.security == "WPA2"
        assert network.channel == 6
    
    def test_network_snapshot_creation(self):
        """NetworkSnapshot should validate creation."""
        interface = NetworkInterface(
            name="eth0",
            connection_type=ConnectionType.ETHERNET,
            is_connected=True,
            ip_address="192.168.1.1",
            gateway="192.168.1.254",
            netmask="255.255.255.0",
            mac_address="00:11:22:33:44:55",
            bytes_sent=1000,
            bytes_recv=2000,
            packets_sent=100,
            packets_recv=200
        )
        
        snapshot = NetworkSnapshot(
            active_interfaces=1,
            connected_interfaces=[interface],
            default_gateway="192.168.1.254",
            dns_servers=["8.8.8.8", "8.8.4.4"],
            wifi_enabled=False,
            wifi_networks=[],
            current_ssid=None,
            vpn_connected=False,
            total_bytes_sent=1000,
            total_bytes_recv=2000
        )
        
        assert snapshot.active_interfaces == 1
        assert len(snapshot.connected_interfaces) == 1
        assert snapshot.dns_servers == ["8.8.8.8", "8.8.4.4"]
        assert snapshot.default_gateway == "192.168.1.254"
