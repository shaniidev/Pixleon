import sys
# Gotta get 'os' so I can stitch paths together.
import os
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QStackedWidget, QFrame
)
from PySide6.QtCore import Qt, QSize, Slot, QPoint
# Gonna need this for pretty icons later on!
from PySide6.QtGui import QIcon

# Time to bring in all the cool tools (widgets)!
from src.widgets.background_remover_widget import BackgroundRemoverWidget
from src.widgets.converter_widget import ConverterWidget
from src.widgets.compressor_widget import CompressorWidget
from src.widgets.resizer_widget import ResizerWidget
from src.widgets.video_compressor_widget import VideoCompressorWidget
# Pulling in the TitleBar, part of the master plan.
from src.widgets.title_bar import TitleBar
# And the About box, 'cause we gotta tell 'em who made this.
from src.widgets.about_dialog import AboutDialog

class PixleonApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixleon - Creative Suite")

        # Okay, let's make this window sleek, no ugly frame!
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.setGeometry(100, 100, 1200, 700)
        self.setMinimumSize(800, 500)

        # Gotta give our app a face! Trying the .ico first.
        icon_path_ico = os.path.join("assets", "icon.ico")
        icon_path_png = os.path.join("assets", "icon.png")
        if os.path.exists(icon_path_ico):
            self.setWindowIcon(QIcon(icon_path_ico))
        elif os.path.exists(icon_path_png):
             print("Warning: icon.ico not found, using icon.png as fallback.")
             self.setWindowIcon(QIcon(icon_path_png))
        else:
            print("Warning: No application icon found in assets folder (icon.ico or icon.png).")

        # Styles first! Gotta look good before we do anything else.
        self._load_styles()

        # Making the main container for all our stuff.
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        # Building the big layout: Title on top, then the sidebar and content side-by-side.
        self._create_main_layout()

        # Start by showing the first tool.
        self.stacked_widget.setCurrentIndex(0)
        # Make the first button look selected, yeah?
        self.sidebar_buttons[0].setChecked(True)

        # Check if we're fullscreen right away and set the button.
        self.title_bar.update_maximize_button(self.isMaximized())

    def _load_styles(self):
        try:
            # Finding the styles file from where we started.
            with open("ui/styles.qss", "r") as f:
                style = f.read()
                self.setStyleSheet(style)
        except FileNotFoundError:
            print("Warning: ui/styles.qss not found. Using default styles.")
        except Exception as e:
            print(f"Error loading styles: {e}")

    def _create_main_layout(self):
        # Making the main box that holds everything top-to-bottom.
        main_v_layout = QVBoxLayout(self.central_widget)
        # No empty space around the edges, pack it tight!
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)

        # First up: Slap that title bar at the top.
        # Make a new title bar thingy.
        self.title_bar = TitleBar(self)
        main_v_layout.addWidget(self.title_bar)

        # Next: A side-by-side layout for the menu and the main view.
        content_h_layout = QHBoxLayout()
        content_h_layout.setContentsMargins(0, 0, 0, 0)
        content_h_layout.setSpacing(0)
        self._create_sidebar(content_h_layout)
        self._create_content_area(content_h_layout)

        # Stick the side-by-side part under the title bar.
        main_v_layout.addLayout(content_h_layout)

        # Tell the main container to use this layout we just built.
        self.central_widget.setLayout(main_v_layout)

        # Hooking up the title bar buttons (minimize, etc.) so they actually do stuff.
        self.title_bar.minimize_requested.connect(self._handle_minimize)
        self.title_bar.maximize_toggle_requested.connect(self._handle_maximize_toggle)
        self.title_bar.close_requested.connect(self._handle_close)
        self.title_bar.move_window_requested.connect(self._handle_move_window)
        # Link the 'About' button too.
        self.title_bar.about_requested.connect(self._show_about_dialog)

    def _create_sidebar(self, main_layout):
        sidebar_frame = QFrame()
        # Giving this a name so we can style it special later.
        sidebar_frame.setObjectName("sidebarFrame")
        # Make the sidebar a bit chubby to fit icons.
        sidebar_frame.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        # A little breathing room between sidebar items.
        sidebar_layout.setSpacing(10)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Here's the list of tools and their icon pictures (hoping they're PNGs in assets!).
        tools = {
            "Background Remover": "background_remover.png",
            "Image Converter": "converter.png",
            "Image Compressor": "compressor.png",
            "Image Resizer": "resizer.png",
            "Video Compressor": "video_compressor.png"
        }

        self.sidebar_buttons = []
        # Just remembering where the pictures live.
        assets_dir = "assets"
        for i, (name, icon_file) in enumerate(tools.items()):
            button = QPushButton(name)
            # These buttons can be 'on' or 'off'.
            button.setCheckable(True)
            # Another name for styling.
            button.setObjectName("sidebarButton")

            # Figure out where the icon picture is and put it on the button.
            icon_path = os.path.join(assets_dir, icon_file)
            if os.path.exists(icon_path):
                button.setIcon(QIcon(icon_path))
                # Make the little picture the right size.
                button.setIconSize(QSize(24, 24))
            else:
                print(f"Warning: Icon not found at {icon_path}")

            # Add those little pop-up hints when you hover.
            button.setToolTip(f"Switch to {name} tool")

            button.clicked.connect(lambda checked, index=i: self._navigate(index))
            sidebar_layout.addWidget(button)
            self.sidebar_buttons.append(button)

        # This shoves everything up so there's empty space at the bottom.
        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar_frame)

    def _create_content_area(self, main_layout):
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QVBoxLayout(content_frame)
        # A bit of cushion inside the main content box.
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(0)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("stackedWidget")

        # Pile up all the different tool screens.
        self.stacked_widget.addWidget(BackgroundRemoverWidget())
        self.stacked_widget.addWidget(ConverterWidget())
        self.stacked_widget.addWidget(CompressorWidget())
        self.stacked_widget.addWidget(ResizerWidget())
        self.stacked_widget.addWidget(VideoCompressorWidget())

        content_layout.addWidget(self.stacked_widget)
        # Let the content area hog more space if the window grows.
        main_layout.addWidget(content_frame, 1)

    def _navigate(self, index):
        self.stacked_widget.setCurrentIndex(index)
        # Make sure only the clicked button looks 'on'.
        for i, button in enumerate(self.sidebar_buttons):
            button.setChecked(i == index)

    # Here's where we tell the minimize/maximize/close buttons what to DO.
    @Slot()
    def _handle_minimize(self):
        self.showMinimized()

    @Slot()
    def _handle_maximize_toggle(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        # Don't need to redraw the button here, the window change thingy does it.

    @Slot()
    def _handle_close(self):
        self.close()

    # This part handles moving the window when you drag the title bar.
    @Slot(QPoint)
    def _handle_move_window(self, new_pos: QPoint):
        """Moves the window to the new absolute position."""
        # The signal tells us exactly where the window should go.
        self.move(new_pos)

    # Code for popping up the 'About' box.
    @Slot()
    def _show_about_dialog(self):
        """Creates and shows the About dialog."""
        # Make the 'About' box belong to the main window.
        about_dialog = AboutDialog(self)
        # Maybe make the dialog look like the main window? (Hmm, commented out for now).
        # about_dialog.setStyleSheet(self.styleSheet())
        # P.S. Might need special style rules for dialogs.
        # Make it so you HAVE to close the 'About' box before doing other stuff.
        about_dialog.exec()

    # Watching for when the window changes (like going fullscreen).
    def changeEvent(self, event):
        """Override to detect window state changes (e.g., maximize)."""
        if event.type() == event.Type.WindowStateChange:
            # If the title bar is there, make sure the maximize button looks right.
            if hasattr(self, 'title_bar') and self.title_bar:
                 self.title_bar.update_maximize_button(self.isMaximized())
        super().changeEvent(event)

# Took out the old run code, main.py handles starting now.
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     window = PixleonApp()
#     window.show()
#     sys.exit(app.exec()) 