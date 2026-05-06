"""
JARVIS Computer Vision Engine
Webcam access, snapshot capture, and face detection
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None
    logger.warning("OpenCV not available, vision features disabled")


@dataclass
class VisionResult:
    success: bool
    message: str
    output_path: Optional[str] = None
    faces_detected: int = 0
    frame_size: Optional[tuple] = None


class VisionEngine:
    """Webcam capture and face detection engine"""

    def __init__(self, camera_index: int = 0, output_dir: Optional[str] = None, cascade_path: Optional[str] = None):
        self.camera_index = camera_index
        self.output_dir = Path(output_dir or Path.cwd() / "captures")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cascade_path = Path(cascade_path) if cascade_path else self._default_cascade_path()
        self.face_cascade = self._load_face_cascade()
        logger.info("Vision engine initialized")

    def _default_cascade_path(self) -> Path:
        workspace_root = Path(__file__).resolve().parents[3]
        return workspace_root / "haarcascade_frontalface_default.xml"

    def _load_face_cascade(self):
        if not cv2:
            return None
        if not self.cascade_path.exists():
            logger.warning(f"Cascade file not found: {self.cascade_path}")
            return None
        cascade = cv2.CascadeClassifier(str(self.cascade_path))
        if cascade.empty():
            logger.warning("Failed to load face cascade")
            return None
        return cascade

    def is_available(self) -> bool:
        return cv2 is not None

    def _open_camera(self):
        if not cv2:
            raise RuntimeError("OpenCV is not available")
        capture = cv2.VideoCapture(self.camera_index)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError("Could not open camera")
        return capture

    def _detect_faces_in_frame(self, frame):
        if not self.face_cascade:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        return faces

    def _annotate_frame(self, frame, faces):
        annotated = frame.copy()
        for (x, y, w, h) in faces:
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 212, 255), 2)
            cv2.putText(annotated, "FACE", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 212, 255), 2)
        return annotated

    def capture_snapshot(self, save_annotated: bool = True) -> Dict[str, Any]:
        """Capture a single frame and optionally annotate detected faces"""
        if not self.is_available():
            return VisionResult(False, "OpenCV is not installed").__dict__

        capture = None
        try:
            capture = self._open_camera()
            ok, frame = capture.read()
            if not ok or frame is None:
                return VisionResult(False, "Could not read from camera").__dict__

            faces = self._detect_faces_in_frame(frame)
            output_frame = self._annotate_frame(frame, faces) if save_annotated and len(faces) and self.face_cascade else frame
            filename = self.output_dir / f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            cv2.imwrite(str(filename), output_frame)

            return VisionResult(
                True,
                f"Snapshot captured with {len(faces)} face(s)",
                output_path=str(filename),
                faces_detected=len(faces),
                frame_size=(frame.shape[1], frame.shape[0]),
            ).__dict__
        except Exception as e:
            logger.error(f"Snapshot capture failed: {e}")
            return VisionResult(False, str(e)).__dict__
        finally:
            if capture is not None:
                capture.release()

    def detect_faces(self, save_annotated: bool = True) -> Dict[str, Any]:
        """Capture a frame, detect faces, and save the result"""
        return self.capture_snapshot(save_annotated=save_annotated)

    def analyze_file(self, image_path: str, save_annotated: bool = False) -> Dict[str, Any]:
        """Analyze a still image for faces"""
        if not self.is_available():
            return VisionResult(False, "OpenCV is not installed").__dict__
        try:
            image = cv2.imread(image_path)
            if image is None:
                return VisionResult(False, "Could not read image file").__dict__
            faces = self._detect_faces_in_frame(image)
            output_path = None
            if save_annotated:
                annotated = self._annotate_frame(image, faces) if self.face_cascade else image
                output_path = str(Path(image_path).with_name(Path(image_path).stem + "_faces.jpg"))
                cv2.imwrite(output_path, annotated)
            return VisionResult(True, f"Detected {len(faces)} face(s)", output_path=output_path, faces_detected=len(faces), frame_size=(image.shape[1], image.shape[0])).__dict__
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return VisionResult(False, str(e)).__dict__


class VisionSetup:
    """Helper for initializing vision components"""

    @staticmethod
    def initialize(camera_index: int = 0, output_dir: Optional[str] = None, cascade_path: Optional[str] = None) -> Dict[str, Any]:
        engine = VisionEngine(camera_index=camera_index, output_dir=output_dir, cascade_path=cascade_path)
        logger.info("Vision components initialized")
        return {"vision_engine": engine}
