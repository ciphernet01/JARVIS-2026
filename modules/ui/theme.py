"""
JARVIS UI Theme
Professional futuristic interface styling
"""

def get_stylesheet() -> str:
    return """
        QMainWindow {
            background-color: #060b14;
        }
        QWidget {
            color: #d7f7ff;
            font-family: 'Segoe UI';
        }
        #RootPanel {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #050913, stop:0.5 #08111f, stop:1 #050913);
        }
        #TopBar, #SideBar, #CenterCard, #RightCard, #LogCard, #InputCard {
            background-color: rgba(9, 19, 34, 215);
            border: 1px solid rgba(58, 174, 255, 80);
            border-radius: 18px;
        }
        QLabel#Title {
            font-size: 28px;
            font-weight: 700;
            color: #8fe6ff;
            letter-spacing: 2px;
        }
        QLabel#Subtitle {
            color: #81c9ff;
            font-size: 12px;
            letter-spacing: 1px;
        }
        QLabel#SectionLabel {
            color: #7adfff;
            font-size: 14px;
            font-weight: 600;
        }
        QLabel#MetricValue {
            color: #ffffff;
            font-size: 20px;
            font-weight: 700;
        }
        QLabel#MetricCaption {
            color: #9eb8c9;
            font-size: 11px;
        }
        QTextBrowser {
            background: rgba(3, 8, 16, 220);
            border: 1px solid rgba(61, 173, 255, 100);
            border-radius: 14px;
            padding: 12px;
            selection-background-color: #2f8cff;
            font-size: 13px;
        }
        QLineEdit {
            background: rgba(3, 8, 16, 230);
            color: #dffbff;
            border: 1px solid rgba(61, 173, 255, 120);
            border-radius: 12px;
            padding: 12px 14px;
            font-size: 13px;
        }
        QLineEdit:focus {
            border: 1px solid #5fd1ff;
        }
        QPushButton {
            background-color: rgba(40, 125, 217, 210);
            color: white;
            border: 1px solid rgba(110, 220, 255, 120);
            border-radius: 12px;
            padding: 10px 16px;
            font-size: 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: rgba(66, 149, 238, 230);
        }
        QPushButton:pressed {
            background-color: rgba(20, 99, 190, 230);
        }
        QPushButton#DangerButton {
            background-color: rgba(170, 45, 61, 210);
        }
        QPushButton#DangerButton:hover {
            background-color: rgba(204, 58, 74, 230);
        }
        QPushButton#GhostButton {
            background-color: rgba(0,0,0,0);
            border: 1px solid rgba(95, 209, 255, 120);
            color: #8fe6ff;
        }
        QPushButton#GhostButton:hover {
            background-color: rgba(95, 209, 255, 18);
        }
        QListWidget {
            background: rgba(3, 8, 16, 220);
            border: 1px solid rgba(61, 173, 255, 100);
            border-radius: 14px;
            padding: 8px;
            font-size: 12px;
        }
        QListWidget::item {
            padding: 8px;
            margin: 2px 0;
            border-radius: 8px;
        }
        QListWidget::item:selected {
            background: rgba(54, 148, 255, 100);
        }
        QStatusBar {
            background: rgba(7, 14, 24, 220);
            color: #99d8ff;
        }
    """
