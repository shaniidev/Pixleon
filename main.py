import sys
from PySide6.QtWidgets import QApplication
# Bringing in the PixleonApp... eventually! Need to make it first.
from src.app import PixleonApp

def main():
    app = QApplication(sys.argv)

    # Making the main window appear! POOF! (Okay, not yet, gotta build it).
    window = PixleonApp()
    window.show()

    # Removed placeholder comments

    sys.exit(app.exec())

if __name__ == "__main__":
    main() 