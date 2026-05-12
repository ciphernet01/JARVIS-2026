"""
CameraManager: Handles camera access, face detection, and vision capabilities.
Provides cross-platform camera device management with efficient snapshot capture.
"""
import base64
import io
import logging
import threading
from dataclasses import dataclass
from typing import Optional, Tuple, List
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not available, camera functionality disabled")


@dataclass(frozen=True)
class CameraSnapshot:
    """Immutable representation of a camera frame snapshot."""
    timestamp: float
    width: int
    height: int
    has_faces: bool
    face_count: int
    face_locations: List[Tuple[int, int, int, int]]  # (x, y, width, height)
    jpeg_base64: Optional[str]  # Base64 encoded JPEG data


@dataclass(frozen=True)
class CameraState:
    """Immutable camera device state."""
    available: bool
    enabled: bool
    device_id: int
    recording: bool
    resolution: Tuple[int, int]
    fps: float
    face_detection_active: bool
    last_face_timestamp: Optional[float]


class CameraManager:
    """
    Singleton camera device manager for vision operations.
    Handles camera access, face detection, and snapshot capture efficiently.
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
        
        self._available = OPENCV_AVAILABLE
        self._enabled = False
        self._device_id = 0
        self._capture = None
        self._recording = False
        self._face_detection_active = False
        self._last_face_timestamp = None
        self._snapshot_lock = threading.Lock()
        self._resolution_cache = (1280, 720)
        self._fps_cache = 30.0
        
        # Load face cascade classifier if available
        self._face_cascade = None
        if self._available:
            try:
                cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                self._face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception as e:
                logger.warning(f"Failed to load face cascade: {e}")
        
        CameraManager._initialized = True
    
    def state(self) -> CameraState:
        """
        Get current camera device state.
        
        Returns:
            CameraState with availability and configuration
        """
        try:
            return CameraState(
                available=self._available,
                enabled=self._enabled,
                device_id=self._device_id,
                recording=self._recording,
                resolution=self._resolution_cache,
                fps=self._fps_cache,
                face_detection_active=self._face_detection_active,
                last_face_timestamp=self._last_face_timestamp
            )
        except Exception as e:
            logger.error(f"Error getting camera state: {e}")
            return CameraState(
                available=False,
                enabled=False,
                device_id=0,
                recording=False,
                resolution=(0, 0),
                fps=0.0,
                face_detection_active=False,
                last_face_timestamp=None
            )
    
    def enable(self) -> bool:
        """
        Enable camera device access.
        
        Returns:
            bool: True if successful
        """
        if not self._available:
            logger.warning("Camera not available")
            return False
        
        if self._enabled and self._capture is not None:
            return True
        
        try:
            self._capture = cv2.VideoCapture(self._device_id)
            if not self._capture.isOpened():
                logger.error("Failed to open camera device")
                self._capture = None
                return False
            
            # Set resolution
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._resolution_cache[0])
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._resolution_cache[1])
            self._capture.set(cv2.CAP_PROP_FPS, self._fps_cache)
            
            self._enabled = True
            logger.info(f"Camera enabled (device {self._device_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to enable camera: {e}")
            self._capture = None
            self._enabled = False
            return False
    
    def disable(self) -> bool:
        """
        Disable camera device access.
        
        Returns:
            bool: True if successful
        """
        try:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            
            self._enabled = False
            self._recording = False
            logger.info("Camera disabled")
            return True
        except Exception as e:
            logger.error(f"Failed to disable camera: {e}")
            return False
    
    def capture_snapshot(self, detect_faces: bool = True) -> Optional[CameraSnapshot]:
        """
        Capture a snapshot from the camera.
        
        Args:
            detect_faces: Whether to perform face detection
            
        Returns:
            CameraSnapshot or None if capture fails
        """
        if not self._enabled or self._capture is None:
            logger.warning("Camera not enabled")
            return None
        
        with self._snapshot_lock:
            try:
                ret, frame = self._capture.read()
                if not ret:
                    logger.error("Failed to read frame from camera")
                    return None
                
                import time
                timestamp = time.time()
                height, width = frame.shape[:2]
                
                # Detect faces if requested
                faces = []
                face_count = 0
                if detect_faces and self._face_cascade is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = self._face_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30)
                    )
                    face_count = len(faces)
                    
                    if face_count > 0:
                        self._last_face_timestamp = timestamp
                        # Draw rectangles on detected faces
                        for (x, y, w, h) in faces:
                            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Encode frame as JPEG base64
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                jpeg_base64 = base64.b64encode(buffer).decode('utf-8')
                
                face_locations = [(int(x), int(y), int(w), int(h)) for x, y, w, h in faces]
                
                return CameraSnapshot(
                    timestamp=timestamp,
                    width=width,
                    height=height,
                    has_faces=face_count > 0,
                    face_count=face_count,
                    face_locations=face_locations,
                    jpeg_base64=jpeg_base64
                )
            except Exception as e:
                logger.error(f"Failed to capture snapshot: {e}")
                return None
    
    def start_face_detection(self) -> bool:
        """
        Start continuous face detection mode.
        
        Returns:
            bool: True if successful
        """
        if not self._available:
            return False
        
        self._face_detection_active = True
        logger.info("Face detection started")
        return True
    
    def stop_face_detection(self) -> bool:
        """
        Stop continuous face detection mode.
        
        Returns:
            bool: True if successful
        """
        self._face_detection_active = False
        self._last_face_timestamp = None
        logger.info("Face detection stopped")
        return True
    
    def set_resolution(self, width: int, height: int) -> bool:
        """
        Set camera resolution.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            
        Returns:
            bool: True if successful
        """
        try:
            self._resolution_cache = (width, height)
            
            if self._capture is not None and self._enabled:
                self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            logger.info(f"Camera resolution set to {width}x{height}")
            return True
        except Exception as e:
            logger.error(f"Failed to set resolution: {e}")
            return False
    
    def list_devices(self) -> List[dict]:
        """
        List available camera devices.
        
        Returns:
            List of device info dictionaries
        """
        if not self._available:
            return []
        
        devices = []
        # Try first 5 device indices
        for i in range(5):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    
                    devices.append({
                        'id': i,
                        'name': f'Camera Device {i}',
                        'resolution': f'{width}x{height}',
                        'fps': int(fps) if fps > 0 else 30
                    })
                    cap.release()
            except Exception as e:
                logger.debug(f"Error checking device {i}: {e}")
        
        return devices if devices else [{'id': 0, 'name': 'Default Camera', 'resolution': '1280x720', 'fps': 30}]
    
    def capability_matrix(self) -> dict:
        """
        Get camera capabilities summary for UI.
        
        Returns:
            dict with capability flags
        """
        return {
            "available": self._available,
            "enabled": self._enabled,
            "can_detect_faces": self._available and self._face_cascade is not None,
            "recording": self._recording,
            "resolution": f"{self._resolution_cache[0]}x{self._resolution_cache[1]}"
        }
    
    def __del__(self):
        """Clean up camera resources on destruction."""
        try:
            if self._capture is not None:
                self._capture.release()
        except Exception as e:
            logger.debug(f"Error releasing camera: {e}")
