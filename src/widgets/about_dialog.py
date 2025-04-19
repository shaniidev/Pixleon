import sys
import os
from PySide6.QtWidgets import (
    QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSpacerItem,
    QSizePolicy, QApplication, QWidget
)
from PySide6.QtCore import Qt, QPoint, QUrl
from PySide6.QtGui import QPixmap, QIcon, QMouseEvent, QDesktopServices

class AboutDialog(QDialog):
    APP_NAME = "Pixleon"
    # Bumped the version number, we're 1.0.0 now!
    APP_VERSION = "1.0.0"
    ABOUT_TEXT = ("Pixleon is a versatile desktop application for quick image and video manipulation, "
                  "offering tools for background removal, format conversion, compression, and resizing.")
    GITHUB_URL = "https://github.com/shaniidev"
    # Swapped the donate link again... hope this one sticks!
    DONATE_URL = "https://www.buymeacoffee.com/shaniidev"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {self.APP_NAME}")
        self.setMinimumWidth(350)
        # No ugly frame for this little pop-up either!
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        # Need this magic line if I want fancy rounded corners later.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Gotta remember where I grabbed the window to drag it.
        self._drag_pos = QPoint()

        # The main container for this whole 'About' box.
        outer_layout = QVBoxLayout(self)
        # Tiny gap around the edge, just in case I add a shadow or something.
        outer_layout.setContentsMargins(1, 1, 1, 1)
        outer_layout.setSpacing(0)

        # Making our own little title bar for this dialog.
        self.title_bar = QWidget()
        # Give it a name so I can style it.
        self.title_bar.setObjectName("dialogTitleBar")
        # How tall should this title bar be? About this tall.
        self.title_bar.setFixedHeight(32)
        title_bar_layout = QHBoxLayout(self.title_bar)
        # Scooch the title text over a bit from the left.
        title_bar_layout.setContentsMargins(5, 0, 0, 0)
        title_bar_layout.setSpacing(5)

        title_label = QLabel(f"About {self.APP_NAME}")
        # Another name for styling.
        title_label.setObjectName("dialogTitleLabel")
        # Could center this text, but nah, left is fine.
        # title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        close_button = QPushButton()
        # Style name for the close button.
        close_button.setObjectName("dialogCloseButton")
        # Where did I put that 'close' picture again? Gotta look relative to here.
        icon_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
        # Using the 'exit' icon for the close button.
        close_icon_path = os.path.join(icon_dir, 'exit.png')
        if os.path.exists(close_icon_path):
            close_button.setIcon(QIcon(close_icon_path))
        else:
            # If the picture's missing, just put an 'X'.
            close_button.setText("X")
            # Making sure the warning message is right if the icon is lost.
            print(f"Warning: exit.png not found at {close_icon_path}")
        # Maybe make this button the same size as the main ones? (Commented out).
        # close_button.setFixedSize(30, 30)
        close_button.clicked.connect(self.accept)

        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(close_button)

        outer_layout.addWidget(self.title_bar)

        # The main box that holds the actual 'About' info.
        content_widget = QWidget()
        # Naming this so I can maybe change its background color.
        content_widget.setObjectName("aboutDialogContent")
        main_layout = QVBoxLayout(content_widget)
        # Some space around the text and icon inside.
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # Section for the app's picture and name.
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        # Let's use the same icon as the main app.
        icon_path = os.path.join(os.path.dirname(__file__), '..', '..', 'assets', "icon.png")
        if os.path.exists(icon_path):
             pixmap = QPixmap(icon_path)
             icon_label.setPixmap(pixmap.scaled(
                 64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
             ))
        name_version_layout = QVBoxLayout()
        name_label = QLabel(f"<b>{self.APP_NAME}</b>")
        name_label.setStyleSheet("font-size: 14pt;")
        version_label = QLabel(f"Version {self.APP_VERSION}")
        version_label.setStyleSheet("color: #a0a5b0;")

        name_version_layout.addWidget(name_label)
        name_version_layout.addWidget(version_label)
        name_version_layout.addStretch()

        header_layout.addWidget(icon_label)
        header_layout.addLayout(name_version_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Here's where I tell people what this app does.
        about_label = QLabel(self.ABOUT_TEXT)
        about_label.setWordWrap(True)
        main_layout.addWidget(about_label)

        # Putting the GitHub and Donate links here.
        links_layout = QHBoxLayout()
        links_layout.setSpacing(15)

        # Making the button that goes to my GitHub page.
        github_button = QPushButton()
        github_button.setObjectName("githubLinkButton")
        github_icon_path = os.path.join(icon_dir, 'github.png')
        if os.path.exists(github_icon_path):
            github_button.setIcon(QIcon(github_icon_path))
        else:
            # If no GitHub picture, just write "GitHub".
            github_button.setText("GitHub")
            print(f"Warning: github.png not found at {github_icon_path}")
        github_button.setToolTip(f"Developer GitHub: {self.GITHUB_URL}")
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.GITHUB_URL)))
        # Could force the size with styles, maybe later.
        # Set fixed size to match title bar buttons if needed via QSS

        # The button for that sweet, sweet coffee money.
        donate_button = QPushButton()
        donate_button.setObjectName("donateButton")
        # Hope I named the coffee icon 'bmc.png'.
        donate_icon_path = os.path.join(icon_dir, 'bmc.png')
        if os.path.exists(donate_icon_path):
            donate_button.setIcon(QIcon(donate_icon_path))
        else:
            # No coffee picture? "Donate" text it is.
            donate_button.setText("Donate")
            print(f"Warning: bmc.png not found at {donate_icon_path}")
        donate_button.setToolTip(f"Support the developer: {self.DONATE_URL}")
        donate_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.DONATE_URL)))
        # This button will just look like a normal button based on the style sheet.
        # Uses default QPushButton style from QSS

        # Shove the links over towards the right.
        links_layout.addStretch()
        # Little text label: "Developed by:".
        links_layout.addWidget(QLabel("Developed by:"))
        links_layout.addWidget(github_button)
        # And another label: "Donate:".
        links_layout.addWidget(QLabel("Donate:"))
        links_layout.addWidget(donate_button)
        links_layout.addStretch()

        # Stick the whole links section under the description text.
        main_layout.addLayout(links_layout)

        # Had an idea for more links here, but commented it out.
        # Optional: Links
        # if hasattr(self, 'REPO_URL'):
        #     link_label = QLabel(f'<a href="{self.REPO_URL}">{self.REPO_URL}</a>')
        #     link_label.setOpenExternalLinks(True)
        #     main_layout.addWidget(link_label)

        # Add some empty space at the bottom to push things up.
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        outer_layout.addWidget(content_widget)
        self.setLayout(outer_layout)

    # Here's the code that lets me drag the frameless dialog around.
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.geometry().contains(event.position().toPoint()):
             # Need to know where the mouse is on the *whole screen* to drag right.
             self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
             event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            # Tell the window to follow the mouse based on screen position.
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        # Forget where I grabbed it once I let go.
        self._drag_pos = QPoint()
        event.accept()

# Code just for running *only* this dialog for testing.
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Should probably load the main styles when testing this alone.
    # You might want to apply the main app style here too for consistent look
    # style_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'styles.qss')
    # try:
    #     with open(style_path, "r") as f:
    #         style = f.read()
    #         app.setStyleSheet(style)
    # except FileNotFoundError:
    #     print(f"Standalone: styles.qss not found at {style_path}.")

    dialog = AboutDialog()
    # Use 'exec()' so it behaves like a real pop-up during the test.
    dialog.exec() 