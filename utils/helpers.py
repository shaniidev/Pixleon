from PySide6.QtWidgets import QFileDialog
from typing import Optional, List, Tuple

# Putting some handy helper functions here, like for popping up file pickers.

def open_file_dialog(parent=None, caption="Open File", filter="All Files (*.*)") -> Optional[str]:
    """Opens a dialog to select a single file."""
    file_path, _ = QFileDialog.getOpenFileName(parent, caption, filter=filter)
    return file_path if file_path else None

def open_files_dialog(parent=None, caption="Open Files", filter="All Files (*.*)") -> Optional[List[str]]:
    """Opens a dialog to select multiple files."""
    file_paths, _ = QFileDialog.getOpenFileNames(parent, caption, filter=filter)
    return file_paths if file_paths else None

def save_file_dialog(parent=None, caption="Save File", default_name="output", filter="All Files (*.*)") -> Optional[str]:
    """Opens a dialog to select a save location and filename."""
    save_path, _ = QFileDialog.getSaveFileName(parent, caption, default_name, filter=filter)
    return save_path if save_path else None

def select_directory_dialog(parent=None, caption="Select Output Folder") -> Optional[str]:
    """Opens a dialog to select a directory."""
    dir_path = QFileDialog.getExistingDirectory(parent, caption)
    return dir_path if dir_path else None

# Can stick more helpful little tools in here later!

# Add more utility functions as needed 