from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

class PlaceholderWidget(QWidget):
    """A simple placeholder widget for tool sections."""
    def __init__(self, tool_name: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(f"{tool_name} Interface - Coming Soon!")
        # Make the text kinda grayed out.
        label.setStyleSheet("font-size: 16pt; color: #808590;")
        layout.addWidget(label)
        self.setLayout(layout) 