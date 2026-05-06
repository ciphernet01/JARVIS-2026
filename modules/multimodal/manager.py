"""
Multimodal Manager
Provides lightweight understanding for files, folders, screenshots, and images.
"""

import json
import logging
import os
import re
from importlib import import_module
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageGrab
except Exception:  # pragma: no cover
    Image = None
    ImageGrab = None

try:
    pytesseract = import_module("pytesseract")
except Exception:  # pragma: no cover
    pytesseract = None

try:
    fitz = import_module("fitz")  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


class MultimodalManager:
    """Understand files, folders, screenshots, and images at a lightweight level."""

    TEXT_EXTENSIONS = {".txt", ".md", ".py", ".json", ".csv", ".log", ".xml", ".html", ".htm", ".ini", ".cfg", ".yaml", ".yml"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"}
    PDF_EXTENSIONS = {".pdf"}
    STOPWORDS = {
        "the", "and", "that", "this", "with", "from", "have", "what", "when",
        "where", "how", "your", "you", "for", "are", "was", "were", "is",
        "it", "a", "an", "to", "of", "in", "on", "at", "by", "be", "as",
        "or", "if", "not", "we", "can", "could", "would", "should", "do",
        "does", "did", "please", "file", "folder", "screen", "image",
    }

    def __init__(self, vision_engine: Any = None):
        self.vision_engine = vision_engine

    def _read_text(self, path: Path, max_chars: int = 12000) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        except Exception:
            return ""

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9']+", (text or "").lower())
        return [token for token in tokens if token not in self.STOPWORDS and len(token) > 2]

    def _top_terms(self, text: str, limit: int = 8) -> List[str]:
        tokens = self._tokenize(text)
        if not tokens:
            return []
        counts = Counter(tokens)
        return [token for token, _ in counts.most_common(limit)]

    def _extract_pdf_text(self, path: Path, max_pages: int = 10) -> str:
        if not fitz:
            return ""
        try:
            document = fitz.open(str(path))
            chunks: List[str] = []
            for page_number in range(min(max_pages, len(document))):
                page = document.load_page(page_number)
                chunks.append(page.get_text())
            return "\n".join(chunks)
        except Exception as exc:
            logger.warning(f"PDF extraction failed for {path}: {exc}")
            return ""

    def _extract_image_text(self, path: Path) -> str:
        if not pytesseract or not Image:
            return ""
        try:
            image = Image.open(str(path))
            return pytesseract.image_to_string(image)
        except Exception as exc:
            logger.warning(f"OCR failed for {path}: {exc}")
            return ""

    def _extract_text_from_file(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in self.TEXT_EXTENSIONS:
            return self._read_text(path)
        if suffix in self.PDF_EXTENSIONS:
            return self._extract_pdf_text(path)
        if suffix in self.IMAGE_EXTENSIONS:
            return self._extract_image_text(path)
        return ""

    def analyze_file(self, file_path: str, include_preview: bool = True) -> Dict[str, Any]:
        """Analyze a file and return a lightweight semantic summary."""
        path = Path(file_path)
        if not path.exists():
            return {"success": False, "error": "File does not exist", "path": str(path)}

        if path.is_dir():
            return self.summarize_folder(file_path)

        text = self._extract_text_from_file(path)
        metadata = {
            "success": True,
            "path": str(path),
            "name": path.name,
            "suffix": path.suffix.lower(),
            "size_bytes": path.stat().st_size,
            "is_text_extracted": bool(text),
            "line_count": len(text.splitlines()) if text else 0,
            "word_count": len(self._tokenize(text)),
            "top_terms": self._top_terms(text),
        }

        if include_preview:
            preview = text.strip().replace("\r\n", "\n")[:1000]
            metadata["preview"] = preview

        if path.suffix.lower() in self.IMAGE_EXTENSIONS:
            metadata["analysis_type"] = "image"
            metadata["ocr_text"] = text[:2000] if text else ""
            if self.vision_engine and hasattr(self.vision_engine, "analyze_file"):
                try:
                    vision_result = self.vision_engine.analyze_file(str(path), save_annotated=False)
                    metadata["face_analysis"] = vision_result
                except Exception as exc:
                    metadata["face_analysis_error"] = str(exc)
        elif path.suffix.lower() in self.PDF_EXTENSIONS:
            metadata["analysis_type"] = "pdf"
        else:
            metadata["analysis_type"] = "text"

        if path.suffix.lower() == ".json":
            try:
                metadata["json_keys"] = list(json.loads(text or "{}").keys())[:20]
            except Exception:
                metadata["json_keys"] = []

        return metadata

    def summarize_folder(self, folder_path: str, max_items: int = 100) -> Dict[str, Any]:
        """Summarize files inside a folder."""
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return {"success": False, "error": "Folder does not exist", "path": str(folder)}

        files = [p for p in folder.rglob("*") if p.is_file()]
        files = files[:max_items]
        type_counts: Counter = Counter()
        summaries: List[Dict[str, Any]] = []

        for file_path in files:
            type_counts[file_path.suffix.lower() or "<no extension>"] += 1
            summaries.append({
                "name": file_path.name,
                "path": str(file_path),
                "suffix": file_path.suffix.lower(),
                "size_bytes": file_path.stat().st_size,
            })

        return {
            "success": True,
            "analysis_type": "folder",
            "path": str(folder),
            "file_count": len(files),
            "file_type_counts": dict(type_counts),
            "files": summaries,
        }

    def summarize_document(self, file_path: str, max_preview_chars: int = 2000) -> Dict[str, Any]:
        """Return a shorter document-style summary for an individual file."""
        analysis = self.analyze_file(file_path, include_preview=True)
        if not analysis.get("success"):
            return analysis

        preview = analysis.get("preview", "") or ""
        lines = preview.splitlines()
        analysis["summary"] = " ".join(lines[:5]).strip()[:max_preview_chars]
        analysis["top_terms"] = analysis.get("top_terms", [])[:5]
        return analysis

    def capture_screen(self, save_path: Optional[str] = None) -> Dict[str, Any]:
        """Capture the screen if supported and analyze the image."""
        if not ImageGrab or not Image:
            return {"success": False, "error": "Screen capture is unavailable"}

        try:
            screenshot = ImageGrab.grab()
            if save_path:
                output_path = Path(save_path)
            else:
                output_path = Path.cwd() / "captures" / "screen_capture.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot.save(str(output_path))

            result = {
                "success": True,
                "path": str(output_path),
                "width": screenshot.width,
                "height": screenshot.height,
            }

            if self.vision_engine and hasattr(self.vision_engine, "analyze_file"):
                try:
                    result["vision"] = self.vision_engine.analyze_file(str(output_path), save_annotated=False)
                except Exception as exc:
                    result["vision_error"] = str(exc)

            if pytesseract:
                try:
                    result["ocr_text"] = pytesseract.image_to_string(screenshot)[:2000]
                except Exception as exc:
                    result["ocr_error"] = str(exc)

            return result
        except Exception as exc:
            logger.error(f"Screen capture failed: {exc}")
            return {"success": False, "error": str(exc)}

    def inspect_path(self, path: str) -> Dict[str, Any]:
        """Route to the appropriate file, folder, or screen summary."""
        return self.analyze_file(path)

    def build_multimodal_brief(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Generate a concise summary suitable for assistant responses."""
        if not path:
            return {
                "success": False,
                "error": "No path provided",
            }

        result = self.inspect_path(path)
        if not result.get("success"):
            return result

        if result.get("analysis_type") == "folder":
            lines = [f"Folder summary: {result['path']} ({result['file_count']} files)"]
            file_types = result.get("file_type_counts", {})
            if file_types:
                lines.append("Types: " + ", ".join(f"{k}={v}" for k, v in list(file_types.items())[:8]))
            result["summary"] = " ".join(lines)
        else:
            title = result.get("name", Path(path).name)
            terms = result.get("top_terms", [])
            preview = result.get("summary") or result.get("preview", "")
            snippet = preview[:240].strip()
            result["summary"] = f"{title}: {snippet}" if snippet else title
            if terms:
                result["summary"] += f" | Topics: {', '.join(terms[:5])}"

        return result
