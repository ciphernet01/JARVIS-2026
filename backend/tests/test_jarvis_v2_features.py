"""
JARVIS Neural Interface API Tests - V2 Features
Tests for face verification login and VSCode extension API
"""

import pytest
import requests
import os
import base64
import numpy as np

# Try to import cv2 for synthetic image generation
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


def create_synthetic_face_image():
    """Create a synthetic image with a face-like pattern for testing"""
    if not CV2_AVAILABLE:
        return None
    
    # Create a 400x400 grayscale image
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    
    # Add a face-like oval in the center
    center = (200, 200)
    axes = (80, 100)  # Face-like oval
    cv2.ellipse(img, center, axes, 0, 0, 360, (200, 180, 160), -1)
    
    # Add eyes
    cv2.circle(img, (170, 180), 15, (50, 50, 50), -1)  # Left eye
    cv2.circle(img, (230, 180), 15, (50, 50, 50), -1)  # Right eye
    
    # Add mouth
    cv2.ellipse(img, (200, 250), (30, 10), 0, 0, 180, (100, 80, 80), -1)
    
    # Encode to base64
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')


def create_blank_image():
    """Create a blank image without any face for testing"""
    if not CV2_AVAILABLE:
        return None
    
    # Create a 400x400 blank image
    img = np.zeros((400, 400, 3), dtype=np.uint8)
    img[:] = (100, 100, 100)  # Gray background
    
    # Encode to base64
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')


# ── Face Verification Login Tests ────────────────────────────────────────────

class TestFaceVerificationLogin:
    """Tests for face verification at login endpoint"""
    
    def test_login_without_image_fallback_mode(self):
        """Test /api/auth/login without image still works (fallback mode)"""
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
        assert "face_detected" in data
        assert "confidence" in data
        # Without image, face_detected should be False
        assert data["face_detected"] is False
        assert data["confidence"] == 0.0
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not available")
    def test_login_with_blank_image_no_face(self):
        """Test /api/auth/login with blank image returns no face detected"""
        blank_image = create_blank_image()
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric", "image": blank_image},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should fail because no face detected
        assert data["success"] is False
        assert data["face_detected"] is False
        assert "No face detected" in data.get("message", "")
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not available")
    def test_login_with_synthetic_face_image(self):
        """Test /api/auth/login with synthetic face image performs detection"""
        face_image = create_synthetic_face_image()
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric", "image": face_image},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        # Response should have face detection fields
        assert "face_detected" in data
        assert "confidence" in data
        # Note: Synthetic face may or may not be detected by Haar cascade
        # The important thing is the endpoint processes the image
    
    def test_login_with_data_uri_prefix(self):
        """Test /api/auth/login handles data URI prefix in image"""
        if not CV2_AVAILABLE:
            pytest.skip("cv2 not available")
        
        face_image = create_synthetic_face_image()
        # Add data URI prefix like browser would send
        image_with_prefix = f"data:image/jpeg;base64,{face_image}"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric", "image": image_with_prefix},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 200
        data = response.json()
        # Should process without error
        assert "face_detected" in data
        assert "confidence" in data
    
    def test_login_with_invalid_base64_image(self):
        """Test /api/auth/login handles invalid base64 gracefully"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric", "image": "not-valid-base64!!!"},
            headers={"Content-Type": "application/json"}
        )
        # Should still return 200 with fallback mode
        assert response.status_code == 200
        data = response.json()
        # Should fall through to biometric_fallback
        assert data["success"] is True


# ── Face Enrollment Tests ────────────────────────────────────────────────────

class TestFaceEnrollment:
    """Tests for face enrollment endpoint"""
    
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
    
    def test_enroll_face_requires_auth(self):
        """Test /api/auth/enroll_face requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/auth/enroll_face",
            json={"image": "test", "label": "owner"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not available")
    def test_enroll_face_with_blank_image(self):
        """Test /api/auth/enroll_face with blank image returns no face"""
        blank_image = create_blank_image()
        response = requests.post(
            f"{BASE_URL}/api/auth/enroll_face",
            json={"image": blank_image, "label": "test_user"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No face detected" in data.get("message", "")
    
    @pytest.mark.skipif(not CV2_AVAILABLE, reason="cv2 not available")
    def test_enroll_face_with_synthetic_face(self):
        """Test /api/auth/enroll_face with synthetic face image"""
        face_image = create_synthetic_face_image()
        response = requests.post(
            f"{BASE_URL}/api/auth/enroll_face",
            json={"image": face_image, "label": "TEST_owner"},
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Response should indicate success or no face detected
        assert "success" in data
        assert "message" in data
    
    def test_enroll_face_with_invalid_image(self):
        """Test /api/auth/enroll_face with invalid image data"""
        response = requests.post(
            f"{BASE_URL}/api/auth/enroll_face",
            json={"image": "invalid-base64", "label": "test"},
            headers=self.headers
        )
        # Should return 400 or 500 for invalid image
        assert response.status_code in [400, 500]


# ── VSCode Extension API Tests ───────────────────────────────────────────────

class TestVSCodeActionEndpoint:
    """Tests for VSCode extension action endpoint"""
    
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
    
    def test_vscode_action_requires_auth(self):
        """Test /api/vscode/action requires X-JARVIS-TOKEN header"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={"action": "explain", "code": "print('hello')"},
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 401
    
    def test_vscode_action_explain(self):
        """Test /api/vscode/action with action=explain returns code explanation"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "explain",
                "code": "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)",
                "language": "python"
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "explain"
        assert "response" in data
        assert len(data["response"]) > 0
        assert "timestamp" in data
    
    def test_vscode_action_fix(self):
        """Test /api/vscode/action with action=fix returns bug fix"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "fix",
                "code": "def add(a, b)\n    return a + b",  # Missing colon
                "language": "python",
                "prompt": "SyntaxError: expected ':'"
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "fix"
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_vscode_action_generate(self):
        """Test /api/vscode/action with action=generate returns generated code"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "generate",
                "prompt": "Write a function to check if a number is prime",
                "language": "python"
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "generate"
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_vscode_action_complete(self):
        """Test /api/vscode/action with action=complete returns completion"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "complete",
                "code": "def greet(name):\n    # Return a greeting message\n    ",
                "language": "python",
                "cursor_line": 3
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "complete"
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_vscode_action_refactor(self):
        """Test /api/vscode/action with action=refactor returns refactored code"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "refactor",
                "code": "x = 1\ny = 2\nz = x + y\nprint(z)",
                "language": "python",
                "prompt": "Use better variable names"
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "refactor"
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_vscode_action_chat(self):
        """Test /api/vscode/action with action=chat returns chat response"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "chat",
                "prompt": "What is the difference between a list and a tuple in Python?",
                "language": "python"
            },
            headers=self.headers,
            timeout=30
        )
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "chat"
        assert "response" in data
        assert len(data["response"]) > 0
    
    def test_vscode_action_unknown_action(self):
        """Test /api/vscode/action with unknown action returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/vscode/action",
            json={
                "action": "unknown_action",
                "code": "print('test')"
            },
            headers=self.headers
        )
        assert response.status_code == 400
        data = response.json()
        assert "Unknown action" in data.get("detail", "")


class TestVSCodeStatusEndpoint:
    """Tests for VSCode extension status endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get auth token before each test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"method": "biometric"},
            headers={"Content-Type": "application/json"}
        )
        self.token = response.json()["token"]
        self.headers = {"X-JARVIS-TOKEN": self.token}
    
    def test_vscode_status_requires_auth(self):
        """Test /api/vscode/status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/vscode/status")
        assert response.status_code == 401
    
    def test_vscode_status_returns_capabilities(self):
        """Test /api/vscode/status returns capabilities list"""
        response = requests.get(
            f"{BASE_URL}/api/vscode/status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert "provider" in data
        assert "capabilities" in data
        assert isinstance(data["capabilities"], list)
        # Check all expected capabilities
        expected_capabilities = ["complete", "explain", "fix", "refactor", "generate", "chat"]
        for cap in expected_capabilities:
            assert cap in data["capabilities"], f"Missing capability: {cap}"
        assert "total_actions" in data
