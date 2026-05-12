"""
NetworkManager: Handles network interface management and WiFi connectivity.
Provides cross-platform network state detection and connection management.
"""
import logging
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional, List, Dict
from enum import Enum

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available, network stats will be limited")


class ConnectionType(Enum):
    """Network connection types."""
    ETHERNET = "ethernet"
    WIFI = "wifi"
    CELLULAR = "cellular"
    VPN = "vpn"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NetworkInterface:
    """Immutable representation of a network interface."""
    name: str
    connection_type: ConnectionType
    is_connected: bool
    ip_address: Optional[str]
    gateway: Optional[str]
    netmask: Optional[str]
    mac_address: Optional[str]
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


@dataclass(frozen=True)
class WiFiNetwork:
    """Immutable representation of a WiFi network."""
    ssid: str
    signal_strength: int  # 0-100, -1 for unknown
    security: str  # "Open", "WPA2", "WPA3", "Mixed", "Unknown"
    frequency: str  # "2.4 GHz" or "5 GHz"
    channel: Optional[int]


@dataclass(frozen=True)
class NetworkSnapshot:
    """Immutable snapshot of network system state."""
    active_interfaces: int
    connected_interfaces: List[NetworkInterface]
    default_gateway: Optional[str]
    dns_servers: List[str]
    wifi_enabled: bool
    wifi_networks: List[WiFiNetwork]
    current_ssid: Optional[str]
    vpn_connected: bool
    total_bytes_sent: int
    total_bytes_recv: int


class NetworkManager:
    """
    Singleton network management system.
    Handles network interface detection, WiFi scanning, and connection management.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._platform = platform.system()
        self._wifi_cache = []
        self._wifi_cache_timestamp = 0
        NetworkManager._initialized = True
    
    def snapshot(self) -> NetworkSnapshot:
        """
        Get comprehensive network system state snapshot.
        
        Returns:
            NetworkSnapshot with interface list and WiFi information
        """
        try:
            interfaces = self._enumerate_interfaces()
            connected = [iface for iface in interfaces if iface.is_connected]
            
            # Get DNS servers
            dns_servers = self._get_dns_servers()
            
            # Get default gateway
            default_gateway = self._get_default_gateway()
            
            # Get WiFi status
            wifi_enabled, current_ssid = self._get_wifi_status()
            
            # Scan for WiFi networks if WiFi is enabled
            wifi_networks = []
            if wifi_enabled:
                wifi_networks = self._scan_wifi_networks()
            
            # Check VPN status
            vpn_connected = self._check_vpn_status()
            
            # Calculate total network stats
            total_sent = sum(iface.bytes_sent for iface in interfaces)
            total_recv = sum(iface.bytes_recv for iface in interfaces)
            
            return NetworkSnapshot(
                active_interfaces=len(interfaces),
                connected_interfaces=connected,
                default_gateway=default_gateway,
                dns_servers=dns_servers,
                wifi_enabled=wifi_enabled,
                wifi_networks=wifi_networks,
                current_ssid=current_ssid,
                vpn_connected=vpn_connected,
                total_bytes_sent=total_sent,
                total_bytes_recv=total_recv
            )
        except Exception as e:
            logger.error(f"Error creating network snapshot: {e}")
            # Return safe default snapshot
            return NetworkSnapshot(
                active_interfaces=0,
                connected_interfaces=[],
                default_gateway=None,
                dns_servers=[],
                wifi_enabled=False,
                wifi_networks=[],
                current_ssid=None,
                vpn_connected=False,
                total_bytes_sent=0,
                total_bytes_recv=0
            )
    
    def _enumerate_interfaces(self) -> List[NetworkInterface]:
        """Enumerate all network interfaces."""
        interfaces = []
        
        try:
            if not PSUTIL_AVAILABLE:
                return interfaces
            
            for name, stats in psutil.net_if_stats().items():
                try:
                    # Get interface addresses
                    addrs = psutil.net_if_addrs().get(name, [])
                    ip_addr = None
                    mac_addr = None
                    
                    for addr in addrs:
                        if addr.family == 2:  # AF_INET - IPv4
                            ip_addr = addr.address
                        elif addr.family == 17:  # AF_LINK - MAC
                            mac_addr = addr.address
                    
                    # Get connection type
                    conn_type = self._detect_connection_type(name)
                    
                    # Get byte counters
                    io_counters = psutil.net_io_counters(pernic=True).get(name)
                    bytes_sent = io_counters.bytes_sent if io_counters else 0
                    bytes_recv = io_counters.bytes_recv if io_counters else 0
                    packets_sent = io_counters.packets_sent if io_counters else 0
                    packets_recv = io_counters.packets_recv if io_counters else 0
                    
                    interface = NetworkInterface(
                        name=name,
                        connection_type=conn_type,
                        is_connected=stats.isup,
                        ip_address=ip_addr,
                        gateway=None,  # Would need routing table
                        netmask=None,   # Would need gethostbyname
                        mac_address=mac_addr,
                        bytes_sent=bytes_sent,
                        bytes_recv=bytes_recv,
                        packets_sent=packets_sent,
                        packets_recv=packets_recv
                    )
                    interfaces.append(interface)
                except Exception as e:
                    logger.debug(f"Error processing interface {name}: {e}")
            
            return interfaces
        except Exception as e:
            logger.warning(f"Failed to enumerate network interfaces: {e}")
            return interfaces
    
    def _detect_connection_type(self, interface_name: str) -> ConnectionType:
        """Detect the type of network connection."""
        name_lower = interface_name.lower()
        
        if any(x in name_lower for x in ['wifi', 'wlan', 'wireless']):
            return ConnectionType.WIFI
        elif any(x in name_lower for x in ['eth', 'ethernet', 'en0', 'en1']):
            return ConnectionType.ETHERNET
        elif any(x in name_lower for x in ['tun', 'tap', 'vpn']):
            return ConnectionType.VPN
        elif any(x in name_lower for x in ['ppp', 'cellular', 'mobile']):
            return ConnectionType.CELLULAR
        
        return ConnectionType.UNKNOWN
    
    def _get_default_gateway(self) -> Optional[str]:
        """Get default gateway IP address."""
        try:
            if not PSUTIL_AVAILABLE:
                return None
            
            gateways = psutil.net_if_gateways()
            if gateways and 'default' in gateways:
                default = gateways['default']
                if default and len(default) > 0:
                    return default[0][0]
        except Exception as e:
            logger.debug(f"Failed to get default gateway: {e}")
        
        return None
    
    def _get_dns_servers(self) -> List[str]:
        """Get configured DNS servers."""
        dns_servers = []
        
        try:
            if self._platform == "Windows":
                result = subprocess.run(
                    ["ipconfig", "/all"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split('\n'):
                    if 'DNS Servers' in line or 'DNS Server' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            server = parts[1].strip()
                            if server and server not in dns_servers:
                                dns_servers.append(server)
            elif self._platform == "Linux":
                # Try /etc/resolv.conf
                try:
                    with open('/etc/resolv.conf', 'r') as f:
                        for line in f:
                            if line.startswith('nameserver'):
                                parts = line.split()
                                if len(parts) > 1:
                                    dns_servers.append(parts[1])
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Failed to get DNS servers: {e}")
        
        return dns_servers[:3]  # Return first 3 DNS servers
    
    def _get_wifi_status(self) -> tuple[bool, Optional[str]]:
        """Get WiFi enabled status and current SSID."""
        try:
            if self._platform == "Windows":
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "State" not in result.stdout:
                    return False, None
                
                for line in result.stdout.split('\n'):
                    if 'State' in line and 'connected' in line.lower():
                        wifi_enabled = True
                        break
                else:
                    wifi_enabled = False
                
                current_ssid = None
                for line in result.stdout.split('\n'):
                    if 'SSID' in line and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            ssid = parts[1].strip()
                            if ssid:
                                current_ssid = ssid
                                break
                
                return wifi_enabled, current_ssid
        except Exception as e:
            logger.debug(f"Failed to get WiFi status: {e}")
        
        return False, None
    
    def _scan_wifi_networks(self) -> List[WiFiNetwork]:
        """Scan for available WiFi networks."""
        networks = []
        
        try:
            if self._platform == "Windows":
                result = subprocess.run(
                    ["netsh", "wlan", "show", "networks", "mode=Bssid"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                current_network = None
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    if 'SSID' in line and ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            ssid = parts[1].strip()
                            if ssid:
                                current_network = {'ssid': ssid}
                    
                    elif 'Authentication' in line and current_network:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            auth = parts[1].strip()
                            current_network['security'] = self._parse_security(auth)
                    
                    elif 'Signal' in line and current_network and '%' in line:
                        try:
                            signal = int(line.split('%')[0].split()[-1])
                            current_network['signal'] = signal
                            networks.append(WiFiNetwork(
                                ssid=current_network.get('ssid', 'Unknown'),
                                signal_strength=signal,
                                security=current_network.get('security', 'Unknown'),
                                frequency="2.4 GHz",  # Simplified
                                channel=None
                            ))
                            current_network = None
                        except (ValueError, IndexError):
                            pass
            
            elif self._platform == "Linux":
                # Try nmcli if available
                result = subprocess.run(
                    ["nmcli", "device", "wifi", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Skip header
                        parts = line.split()
                        if len(parts) >= 7:
                            ssid = parts[0]
                            security = ' '.join(parts[4:])
                            signal = int(parts[6])
                            
                            networks.append(WiFiNetwork(
                                ssid=ssid,
                                signal_strength=signal,
                                security=security,
                                frequency="2.4 GHz",
                                channel=None
                            ))
        except Exception as e:
            logger.debug(f"Failed to scan WiFi networks: {e}")
        
        return networks[:10]  # Return first 10 networks
    
    def _parse_security(self, security_str: str) -> str:
        """Parse security type from raw string."""
        s = security_str.upper()
        if "WPA3" in s:
            return "WPA3"
        elif "WPA2" in s or "WPA" in s:
            return "WPA2"
        elif "OPEN" in s or "NONE" in s:
            return "Open"
        else:
            return "Unknown"
    
    def _check_vpn_status(self) -> bool:
        """Check if VPN is connected."""
        try:
            if not PSUTIL_AVAILABLE:
                return False
            
            interfaces = psutil.net_if_stats()
            for name in interfaces:
                if any(x in name.lower() for x in ['tun', 'tap', 'vpn']):
                    if interfaces[name].isup:
                        return True
        except Exception as e:
            logger.debug(f"Failed to check VPN status: {e}")
        
        return False
    
    def capability_matrix(self) -> dict:
        """
        Get network capabilities for UI.
        
        Returns:
            dict with capability flags
        """
        snapshot = self.snapshot()
        return {
            "has_ethernet": any(i.connection_type == ConnectionType.ETHERNET for i in snapshot.connected_interfaces),
            "has_wifi": any(i.connection_type == ConnectionType.WIFI for i in snapshot.connected_interfaces),
            "wifi_enabled": snapshot.wifi_enabled,
            "connected_interface_count": len(snapshot.connected_interfaces),
            "vpn_connected": snapshot.vpn_connected,
            "has_internet": len(snapshot.connected_interfaces) > 0
        }
