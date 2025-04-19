import sys
import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QHBoxLayout, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, Signal, QPoint
from PySide6.QtGui import QIcon, QPixmap, QMouseEvent

class TitleBar(QWidget):
    """Custom Title Bar widget for the frameless window."""

    # These tell the main window, 'Hey, user wants to minimize!' or whatever.
    minimize_requested = Signal()
    maximize_toggle_requested = Signal()
    close_requested = Signal()
    # And this one is for popping up the 'About' box.
    about_requested = Signal()
    # This signal shouts out where the window should move when I drag it.
    move_window_requested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        # How tall? This tall. Might need to tweak if icons look weird.
        self.setFixedHeight(35)
        self._mouse_pressed = False
        self._mouse_press_pos = QPoint(0, 0)
        self._window_pos_before_move = QPoint(0, 0)

        layout = QHBoxLayout(self)
        # A little space on the right so the close button isn't squished.
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(0)

        # Little picture on the left. Could skip this, main window has one too.
        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("titleIcon")
        # Use PNG pictures usually work best here.
        icon_path = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            self.icon_label.setPixmap(pixmap.scaled(
                # Scale icon reasonably
                QSize(22, 22),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        self.icon_label.setFixedSize(QSize(30, 30))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # The app's name in the middle. Could change this text later maybe.
        self.title_label = QLabel("Pixleon - Creative Suite", self)
        self.title_label.setObjectName("titleLabel")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        # This invisible thing shoves the buttons all the way to the right.
        layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Minimize, Maximize, Close buttons go here!
        # How big should the buttons be? This big looks okay.
        button_size = QSize(30, 30)
        # The actual pictures inside the buttons should be a bit smaller.
        icon_size = QSize(16, 16)
        assets_dir = "assets"

        # Let's grab all the button pictures.
        # Picture for the 'About' button.
        self.about_icon = QIcon(os.path.join(assets_dir, "info.png"))
        self.minimize_icon = QIcon(os.path.join(assets_dir, "minus.png"))
        self.maximize_icon = QIcon(os.path.join(assets_dir, "maximize.png"))
        # Hoping I have a 'restore down' picture, if not, just use the maximize one again.
        restore_icon_path = os.path.join(assets_dir, "restore.png")
        self.restore_icon = QIcon(restore_icon_path) if os.path.exists(restore_icon_path) else self.maximize_icon
        self.close_icon = QIcon(os.path.join(assets_dir, "exit.png"))

        # Putting the 'About' button first, before minimize.
        self.about_button = QPushButton(self)
        self.about_button.setObjectName("aboutButton")
        self.about_button.setFixedSize(button_size)
        self.about_button.setIcon(self.about_icon)
        self.about_button.setIconSize(icon_size)
        self.about_button.setToolTip("About Pixleon")
        layout.addWidget(self.about_button)

        self.minimize_button = QPushButton(self)
        self.minimize_button.setObjectName("minimizeButton")
        self.minimize_button.setFixedSize(button_size)
        self.minimize_button.setIcon(self.minimize_icon)
        self.minimize_button.setIconSize(icon_size)
        self.minimize_button.setToolTip("Minimize")
        layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton(self)
        self.maximize_button.setObjectName("maximizeButton")
        self.maximize_button.setFixedSize(button_size)
        # What the maximize button looks like at first.
        self.maximize_button.setIcon(self.maximize_icon)
        self.maximize_button.setIconSize(icon_size)
        self.maximize_button.setToolTip("Maximize")
        layout.addWidget(self.maximize_button)

        self.close_button = QPushButton(self)
        self.close_button.setObjectName("closeButton")
        self.close_button.setFixedSize(button_size)
        self.close_button.setIcon(self.close_icon)
        self.close_button.setIconSize(icon_size)
        self.close_button.setToolTip("Close")
        layout.addWidget(self.close_button)

        self.setLayout(layout)

        # Hook up the buttons so they send out those signals we defined earlier.
        # Don't forget to connect the 'About' button!
        self.about_button.clicked.connect(self.about_requested.emit)
        self.minimize_button.clicked.connect(self.minimize_requested.emit)
        self.maximize_button.clicked.connect(self.maximize_toggle_requested.emit)
        self.close_button.clicked.connect(self.close_requested.emit)

    # This makes the maximize button change its look (to 'restore') when the window is full screen.
    def update_maximize_button(self, is_maximized: bool):
        if is_maximized:
            self.maximize_button.setIcon(self.restore_icon)
            self.maximize_button.setToolTip("Restore")
        else:
            self.maximize_button.setIcon(self.maximize_icon)
            self.maximize_button.setToolTip("Maximize")

    # Here's the magic for letting the user drag the window by the title bar.
    def mousePressEvent(self, event: QMouseEvent):
        """Capture mouse press position for dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            # Make sure they didn't click a button when trying to drag.
            # Basically, if they clicked the icon or the title text, it's probably okay to drag.
            if self.childAt(event.position().toPoint()) in [None, self.title_label, self.icon_label]:
                self._mouse_pressed = True
                # Need mouse position on the *whole screen*.
                self._mouse_press_pos = event.globalPosition().toPoint()
                # Remember where the window *was* before we started moving it.
                # Finding the actual main window can be tricky sometimes.
                # A better way would be to ask the main app directly where it is.
                # For now, I'll just *assume* the parent is the window I need.
                # Trying to find the main window this belongs to.
                parent_window = self.window()
                if parent_window:
                    self._window_pos_before_move = parent_window.pos()
                else:
                    # If I can't find the main window, I can't drag it!
                    self._mouse_pressed = False
                event.accept()
            else:
                # If they clicked a button, let the button do its thing.
                event.ignore()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Move the window if dragging."""
        if self._mouse_pressed:
            # How far has the mouse moved since they first clicked?
            delta = event.globalPosition().toPoint() - self._mouse_press_pos
            # Figure out where the window's top-left corner *should* be now.
            new_window_pos = self._window_pos_before_move + delta
            # Send out the signal telling the main app the *exact* new coordinates.
            self.move_window_requested.emit(new_window_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Release mouse button."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_pressed = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    # Little extra: double-clicking the title bar maximizes/restores.
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
             # Only maximize if they double-clicked the empty space, not a button.
             if self.childAt(event.position().toPoint()) in [None, self.title_label, self.icon_label]:
                self.maximize_toggle_requested.emit()
                event.accept()
             else:
                 event.ignore()
        else:
            super().mouseDoubleClickEvent(event)

# Code just for testing this title bar by itself.
if __name__ == '__main__':
    # Need this import just for the test.
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # Some simple colors and stuff so the test looks okay.
    app.setStyleSheet("""
        #titleBar { background-color: #333; border-bottom: 1px solid #555; }
        #titleLabel { color: white; padding-left: 5px; font-weight: bold; }
        #minimizeButton, #maximizeButton, #closeButton {
            background-color: transparent;
            color: white;
            border: none;
            font-size: 14pt;
            /* Trying a font that might have nicer-looking minimize/maximize symbols. */
            font-family: 'Segoe UI Symbol';
        }
        #minimizeButton:hover, #maximizeButton:hover { background-color: #555; }
        #closeButton:hover { background-color: #e81123; }
        #minimizeButton:pressed, #maximizeButton:pressed { background-color: #777; }
        #closeButton:pressed { background-color: #f1707a; }
    """)
    title_bar = TitleBar()
    title_bar.show()
    sys.exit(app.exec()) 