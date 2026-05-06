"""
JARVIS Neural Interface API Tests
Tests all backend endpoints for the JARVIS AI Assistant
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health check endpoint tests - no auth required"""
    
    def test_health_returns_online(self):
        """Test /api/health returns status online"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert data["system"] == "JARVIS Neural Interface"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data


class TestAuthEndpoint:
    """Authentication endpoint tests"""
    
    def test_login_biometric_success(self):
        """Test /api/auth/login returns token with biometric method"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data
        assert len(data["token"]) > 0
        assert "message" in data
        assert "user" in data
        assert data["user"]["name"] == "Sir"
    
    def test_login_default_method(self):
        """Test /api/auth/login works with default method"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "token" in data


class TestProtectedEndpoints:
    """Tests for endpoints requiring authentication"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"},
            headers={"Content-Type": "application/json"}
        )
        self.token = response.json()["token"]
        self.headers = {
            "Content-Type": "application/json",
            "X-JARVIS-TOKEN": self.token
        }
    
    def test_unauthorized_without_token(self):
        """Test protected endpoints return 401 without token"""
        response = requests.get(f"{BASE_URL}/api/system/metrics")
        assert response.status_code == 401
    
    def test_unauthorized_with_invalid_token(self):
        """Test protected endpoints return 401 with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/system/metrics",
            headers={"X-JARVIS-TOKEN": "invalid-token-123"}
        )
        assert response.status_code == 401


class TestSystemMetrics:
    """System metrics endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {"X-JARVIS-TOKEN": self.token}
    
    def test_system_metrics_returns_cpu_data(self):
        """Test /api/system/metrics returns CPU data"""
        response = requests.get(f"{BASE_URL}/api/system/metrics", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "cpu" in data
        assert "percent" in data["cpu"]
        assert "cores" in data["cpu"]
    
    def test_system_metrics_returns_memory_data(self):
        """Test /api/system/metrics returns memory data"""
        response = requests.get(f"{BASE_URL}/api/system/metrics", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data
        assert "percent" in data["memory"]
        assert "total_gb" in data["memory"]
        assert "used_gb" in data["memory"]
    
    def test_system_metrics_returns_disk_data(self):
        """Test /api/system/metrics returns disk data"""
        response = requests.get(f"{BASE_URL}/api/system/metrics", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "disk" in data
        assert "percent" in data["disk"]
        assert "total_gb" in data["disk"]


class TestWeatherEndpoint:
    """Weather endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {"X-JARVIS-TOKEN": self.token}
    
    def test_weather_returns_data(self):
        """Test /api/weather returns weather data"""
        response = requests.get(f"{BASE_URL}/api/weather", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        # Weather may return error if service unavailable, but should have structure
        if "error" not in data:
            assert "temp_c" in data
            assert "description" in data
            assert "location" in data


class TestStatusEndpoint:
    """System status endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {"X-JARVIS-TOKEN": self.token}
    
    def test_status_returns_online(self):
        """Test /api/status returns online status"""
        response = requests.get(f"{BASE_URL}/api/status", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "llm_provider" in data
        assert "llm_available" in data
        assert "skills" in data
        assert isinstance(data["skills"], list)


class TestCommandEndpoint:
    """Command processing endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {
            "Content-Type": "application/json",
            "X-JARVIS-TOKEN": self.token
        }
    
    def test_command_processes_simple_query(self):
        """Test /api/command processes a simple command"""
        response = requests.post(
            f"{BASE_URL}/api/command",
            json={"command": "What is 2+2?"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert "timestamp" in data
    
    def test_command_rejects_empty_command(self):
        """Test /api/command rejects empty command"""
        response = requests.post(
            f"{BASE_URL}/api/command",
            json={"command": ""},
            headers=self.headers
        )
        assert response.status_code == 400
    
    def test_command_rejects_whitespace_only(self):
        """Test /api/command rejects whitespace-only command"""
        response = requests.post(
            f"{BASE_URL}/api/command",
            json={"command": "   "},
            headers=self.headers
        )
        assert response.status_code == 400


class TestCodeAssistEndpoint:
    """Code assistance endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {
            "Content-Type": "application/json",
            "X-JARVIS-TOKEN": self.token
        }
    
    def test_code_assist_generates_code(self):
        """Test /api/code/assist generates code response"""
        response = requests.post(
            f"{BASE_URL}/api/code/assist",
            json={"prompt": "Write a hello world function", "language": "python"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        assert "timestamp" in data
    
    def test_code_assist_accepts_different_languages(self):
        """Test /api/code/assist accepts different language options"""
        response = requests.post(
            f"{BASE_URL}/api/code/assist",
            json={"prompt": "Write hello world", "language": "javascript"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data


class TestLLMStatusEndpoint:
    """LLM status endpoint tests - no auth required"""
    
    def test_llm_status_returns_providers(self):
        """Test /api/llm/status returns LLM provider info"""
        response = requests.get(f"{BASE_URL}/api/llm/status")
        assert response.status_code == 200
        data = response.json()
        assert "gemini" in data
        assert "ollama" in data
        assert "available" in data["gemini"]
        assert "model" in data["gemini"]


class TestHistoryEndpoint:
    """Conversation history endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"}
        )
        self.token = response.json()["token"]
        self.headers = {"X-JARVIS-TOKEN": self.token}
    
    def test_history_returns_list(self):
        """Test /api/history returns conversation history"""
        response = requests.get(f"{BASE_URL}/api/history", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)
