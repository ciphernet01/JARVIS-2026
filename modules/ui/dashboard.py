"""
Professional JARVIS Dashboard
Futuristic desktop interface inspired by HUD-style assistant systems
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from .theme import get_stylesheet

logger = logging.getLogger(__name__)


class OrbWidget(QtWidgets.QWidget):
    """Animated glowing orb for the center panel"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pulse = 0.0
        self._glow = 0.7
        self.setMinimumSize(280, 280)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._animate)
        self.timer.start(35)

    def _animate(self):
        self._pulse += 0.055
        self._glow = 0.6 + (0.4 * (1 + math.sin(self._pulse)) / 2)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        center = rect.center()

        # Outer glow
        for i, alpha in enumerate([22, 40, 60, 90]):
            radius = 120 + i * 18 + int(10 * math.sin(self._pulse + i))
            color = QtGui.QColor(46, 174, 255, alpha)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(center, radius, radius)

        # Orb core
        gradient = QtGui.QRadialGradient(center, 110)
        gradient.setColorAt(0.0, QtGui.QColor(255, 255, 255, 230))
        gradient.setColorAt(0.15, QtGui.QColor(142, 234, 255, 210))
        gradient.setColorAt(0.6, QtGui.QColor(36, 136, 255, 180))
        gradient.setColorAt(1.0, QtGui.QColor(10, 28, 50, 0))
        painter.setBrush(gradient)
        painter.drawEllipse(center, 96, 96)

        # Grid rings
        pen = QtGui.QPen(QtGui.QColor(120, 220, 255, 140), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        for radius in (44, 72, 104):
            painter.drawEllipse(center, radius, radius)

        # Crosshair
        pen = QtGui.QPen(QtGui.QColor(170, 245, 255, 170), 1)
        painter.setPen(pen)
        painter.drawLine(center.x() - 140, center.y(), center.x() + 140, center.y())
        painter.drawLine(center.x(), center.y() - 140, center.x(), center.y() + 140)

        # Label
        painter.setPen(QtGui.QColor(220, 248, 255))
        font = QtGui.QFont("Segoe UI", 12, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.drawText(rect, QtCore.Qt.AlignCenter, "JARVIS")


class CommandWorker(QtCore.QThread):
    """Process commands without blocking the UI"""

    response_ready = QtCore.pyqtSignal(str)
    error_ready = QtCore.pyqtSignal(str)
    started_processing = QtCore.pyqtSignal(str)
    finished_processing = QtCore.pyqtSignal()

    def __init__(
        self,
        assistant,
        command: str,
        speak: bool = False,
        voice_capture: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.assistant = assistant
        self.command = command
        self.speak = speak
        self.voice_capture = voice_capture

    def run(self):  # noqa: D401
        try:
            self.started_processing.emit(self.command)
            if self.voice_capture:
                spoken = self.assistant.recognizer.listen_once()
                if not spoken:
                    self.error_ready.emit("No voice input detected")
                    return
                self.assistant.conversation_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "user",
                    "text": spoken,
                })
                response = self.assistant._process_input(spoken)
            else:
                response = self.assistant._process_input(self.command)
            if self.speak and self.assistant.synthesizer:
                try:
                    self.assistant.synthesizer.speak(response)
                except Exception as speak_error:
                    logger.warning(f"TTS failed: {speak_error}")
            self.response_ready.emit(response)
        except Exception as e:
            logger.exception("Failed to process command")
            self.error_ready.emit(str(e))
        finally:
            self.finished_processing.emit()


class JARVISDashboard(QtWidgets.QMainWindow):
    """Modern HUD-style JARVIS interface"""

    def __init__(self, assistant, config, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self.config = config
        self.worker: Optional[CommandWorker] = None
        self.setWindowTitle("JARVIS // Neural Interface")
        self.resize(1600, 960)
        self.setMinimumSize(1280, 800)
        self.setStyleSheet(get_stylesheet())
        self._build_ui()
        self._wire_events()
        self._refresh_clock()
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.timeout.connect(self._refresh_clock)
        self.clock_timer.start(1000)
        self._append_system_message("JARVIS online. Neural interface ready.")
        self._append_system_message("Professional HUD loaded without external image assets.")

    def _build_ui(self):
        central = QtWidgets.QWidget(self)
        central.setObjectName("RootPanel")
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        self.top_bar = QtWidgets.QFrame()
        self.top_bar.setObjectName("TopBar")
        top_layout = QtWidgets.QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(18, 14, 18, 14)
        top_layout.setSpacing(12)

        title_box = QtWidgets.QVBoxLayout()
        self.title_label = QtWidgets.QLabel("JARVIS")
        self.title_label.setObjectName("Title")
        self.subtitle_label = QtWidgets.QLabel("NEURAL ASSISTANT INTERFACE // HUD CONTROL")
        self.subtitle_label.setObjectName("Subtitle")
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.subtitle_label)

        self.clock_label = QtWidgets.QLabel("--:--:--")
        self.clock_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.clock_label.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")

        self.status_chip = QtWidgets.QLabel("SYSTEM READY")
        self.status_chip.setAlignment(QtCore.Qt.AlignCenter)
        self.status_chip.setStyleSheet(
            "background-color: rgba(35, 164, 104, 200); color: white; padding: 8px 14px; border-radius: 10px; font-weight: 700;"
        )

        top_layout.addLayout(title_box, 1)
        top_layout.addWidget(self.status_chip)
        top_layout.addWidget(self.clock_label)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(14)

        self.left_panel = QtWidgets.QFrame()
        self.left_panel.setObjectName("SideBar")
        left_layout = QtWidgets.QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(16, 16, 16, 16)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._metric_card("ACTIVE USER", "default_user", "Current session identity"))
        left_layout.addWidget(self._metric_card("MODE", "Interactive", "Typing and voice supported"))
        left_layout.addWidget(self._metric_card("ENGINE", "Modular Core", "Security + persistence enabled"))

        quick_label = QtWidgets.QLabel("QUICK COMMANDS")
        quick_label.setObjectName("SectionLabel")
        left_layout.addWidget(quick_label)

        self.quick_list = QtWidgets.QListWidget()
        self.quick_list.addItems([
            "what time is it",
            "what date is today",
            "show help",
            "system info",
            "weather in London",
            "search for openai",
        ])
        left_layout.addWidget(self.quick_list, 1)

        self.voice_button = QtWidgets.QPushButton("VOICE COMMAND")
        self.clear_button = QtWidgets.QPushButton("CLEAR LOG")
        self.clear_button.setObjectName("GhostButton")
        left_layout.addWidget(self.voice_button)
        left_layout.addWidget(self.clear_button)

        self.center_panel = QtWidgets.QFrame()
        self.center_panel.setObjectName("CenterCard")
        center_layout = QtWidgets.QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(18, 18, 18, 18)
        center_layout.setSpacing(12)

        self.orb = OrbWidget()
        self.orb_caption = QtWidgets.QLabel("NEURAL CORE ACTIVE")
        self.orb_caption.setAlignment(QtCore.Qt.AlignCenter)
        self.orb_caption.setObjectName("SectionLabel")

        self.log_card = QtWidgets.QFrame()
        self.log_card.setObjectName("LogCard")
        log_layout = QtWidgets.QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(8)
        log_title = QtWidgets.QLabel("CONVERSATION STREAM")
        log_title.setObjectName("SectionLabel")
        self.log_view = QtWidgets.QTextBrowser()
        self.log_view.setOpenExternalLinks(True)
        log_layout.addWidget(log_title)
        log_layout.addWidget(self.log_view)

        self.input_card = QtWidgets.QFrame()
        self.input_card.setObjectName("InputCard")
        input_layout = QtWidgets.QHBoxLayout(self.input_card)
        input_layout.setContentsMargins(14, 14, 14, 14)
        input_layout.setSpacing(10)
        self.input_box = QtWidgets.QLineEdit()
        self.input_box.setPlaceholderText("Issue a command... e.g. 'what time is it' or 'search for Tesla news'")
        self.send_button = QtWidgets.QPushButton("SEND")
        self.stop_button = QtWidgets.QPushButton("TERMINATE")
        self.stop_button.setObjectName("DangerButton")
        input_layout.addWidget(self.input_box, 1)
        input_layout.addWidget(self.send_button)
        input_layout.addWidget(self.stop_button)

        center_layout.addWidget(self.orb)
        center_layout.addWidget(self.orb_caption)
        center_layout.addWidget(self.log_card, 1)
        center_layout.addWidget(self.input_card)

        self.right_panel = QtWidgets.QFrame()
        self.right_panel.setObjectName("RightCard")
        right_layout = QtWidgets.QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        right_layout.addWidget(self._metric_card("SKILLS", str(len(self.assistant.skill_registry.skills) if self.assistant.skill_registry else 0), "Registered integrations"))
        right_layout.addWidget(self._metric_card("CONVERSATIONS", str(len(self.assistant.conversation_history)), "Session log entries"))
        right_layout.addWidget(self._metric_card("PERSISTENCE", "ONLINE" if self.assistant.persistence else "OFFLINE", "Database backed storage"))

        side_label = QtWidgets.QLabel("SYSTEM STATUS")
        side_label.setObjectName("SectionLabel")
        right_layout.addWidget(side_label)

        self.system_list = QtWidgets.QListWidget()
        self.system_list.addItems([
            "Security: active",
            "Database: connected",
            "Skill engine: loaded",
            "UI: immersive",
        ])
        right_layout.addWidget(self.system_list, 1)

        right_layout.addWidget(self._action_button("Export transcript", self._export_transcript))
        right_layout.addWidget(self._action_button("Refresh metrics", self._refresh_metrics))

        body.addWidget(self.left_panel, 1)
        body.addWidget(self.center_panel, 2)
        body.addWidget(self.right_panel, 1)

        root.addWidget(self.top_bar)
        root.addLayout(body, 1)

        self.statusBar().showMessage("JARVIS ready")

    def _metric_card(self, caption: str, value: str, subtitle: str) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        card.setStyleSheet(
            "QFrame { background-color: rgba(3, 8, 16, 200); border: 1px solid rgba(61, 173, 255, 90); border-radius: 14px; }"
        )
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        caption_label = QtWidgets.QLabel(caption)
        caption_label.setObjectName("MetricCaption")
        value_label = QtWidgets.QLabel(value)
        value_label.setObjectName("MetricValue")
        subtitle_label = QtWidgets.QLabel(subtitle)
        subtitle_label.setStyleSheet("color: #8caac0; font-size: 11px;")
        layout.addWidget(caption_label)
        layout.addWidget(value_label)
        layout.addWidget(subtitle_label)
        return card

    def _action_button(self, text: str, callback) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        return button

    def _wire_events(self):
        self.send_button.clicked.connect(self._submit_command)
        self.input_box.returnPressed.connect(self._submit_command)
        self.clear_button.clicked.connect(self.log_view.clear)
        self.stop_button.clicked.connect(self.close)
        self.voice_button.clicked.connect(self._voice_command)
        self.quick_list.itemDoubleClicked.connect(self._use_quick_command)

    def _refresh_clock(self):
        self.clock_label.setText(datetime.now().strftime("%a %d %b %Y  %H:%M:%S"))

    def _append_system_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'<span style="color:#7fcfff">[{timestamp}] SYSTEM</span><br>'
            f'<span style="color:#e9fbff">{message}</span><br><br>'
        )
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _append_user_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'<span style="color:#8fe6ff">[{timestamp}] YOU</span><br>'
            f'<span style="color:#ffffff">{message}</span><br><br>'
        )
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _append_assistant_message(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(
            f'<span style="color:#9df0a4">[{timestamp}] JARVIS</span><br>'
            f'<span style="color:#dffbff">{message}</span><br><br>'
        )
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def _use_quick_command(self, item):
        self.input_box.setText(item.text())
        self._submit_command()

    def _submit_command(self):
        command = self.input_box.text().strip()
        if not command:
            return
        self.input_box.clear()
        self._append_user_message(command)
        self.status_chip.setText("PROCESSING")
        self.status_chip.setStyleSheet(
            "background-color: rgba(199, 155, 44, 220); color: white; padding: 8px 14px; border-radius: 10px; font-weight: 700;"
        )
        self._start_worker(command, speak=True)

    def _voice_command(self):
        recognizer = self.assistant.recognizer
        if not recognizer:
            self._append_system_message("Speech recognizer is unavailable.")
            return
        self._append_system_message("Listening for a single command...")
        self._start_worker("voice", speak=True, voice_capture=True)

    def _start_worker(self, command: str, speak: bool = False, voice_capture: bool = False):
        if self.worker and self.worker.isRunning():
            self._append_system_message("Assistant is still processing the previous command.")
            return

        self.worker = CommandWorker(self.assistant, command, speak=speak, voice_capture=voice_capture, parent=self)
        self.worker.started_processing.connect(lambda _: None)
        self.worker.response_ready.connect(self._handle_response)
        self.worker.error_ready.connect(self._handle_error)
        self.worker.finished_processing.connect(self._handle_finished)
        self.worker.start()

    def _handle_response(self, response: str):
        self._append_assistant_message(response)
        self.status_chip.setText("SYSTEM READY")
        self.status_chip.setStyleSheet(
            "background-color: rgba(35, 164, 104, 200); color: white; padding: 8px 14px; border-radius: 10px; font-weight: 700;"
        )
        self._refresh_metrics()

    def _handle_error(self, error: str):
        self._append_system_message(f"Error: {error}")
        self.status_chip.setText("ERROR")
        self.status_chip.setStyleSheet(
            "background-color: rgba(170, 45, 61, 210); color: white; padding: 8px 14px; border-radius: 10px; font-weight: 700;"
        )

    def _handle_finished(self):
        if self.status_chip.text() != "ERROR":
            self.status_chip.setText("SYSTEM READY")

    def _refresh_metrics(self):
        if self.assistant.skill_registry:
            self.system_list.clear()
            self.system_list.addItems([
                f"Security: {'active' if self.assistant.security else 'offline'}",
                f"Database: {'connected' if self.assistant.persistence else 'offline'}",
                f"Skills: {len(self.assistant.skill_registry.skills)} loaded",
                f"Conversations: {len(self.assistant.conversation_history)} logged",
            ])

    def _export_transcript(self):
        text = self.log_view.toPlainText().strip()
        if not text:
            self._append_system_message("Nothing to export yet.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export transcript", "jarvis_transcript.txt", "Text files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._append_system_message(f"Transcript exported to {path}")
        except Exception as e:
            self._append_system_message(f"Export failed: {e}")
