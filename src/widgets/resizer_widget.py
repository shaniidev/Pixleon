import sys
import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QLineEdit, QProgressBar, QMessageBox, QListWidgetItem, QSizePolicy,
    QSpinBox, QCheckBox, QComboBox, QFrame # Added boxes and dropdowns for size and stuff.
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor
# Need Pillow Image library just to get those filter names.
from PIL import Image

# Helpers, again.
try:
    # Proper.
    from utils.helpers import open_files_dialog, select_directory_dialog
except ImportError as e:
    print(f"ERROR importing helpers: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    def open_files_dialog(*args, **kwargs): return None
    def select_directory_dialog(*args, **kwargs): return None

# Worker for resizing.
try:
    # Yes.
    from utils.image_processing import ImageResizingWorker
except ImportError as e:
    print(f"ERROR importing ImageResizingWorker: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # Fake resizer.
    class ImageResizingWorker(QThread):
        progress = Signal(int, int)
        file_processed = Signal(str, str)
        error = Signal(str)
        def __init__(self, *args, **kwargs): super().__init__()
        def run(self): self.error.emit("Worker not loaded!")
        def stop(self): pass

class ResizerWidget(QWidget):
    # Turning the fancy filter names into the codes Pillow understands.
    RESAMPLE_FILTERS = {
        "Nearest Neighbor": Image.Resampling.NEAREST,
        "Bilinear": Image.Resampling.BILINEAR,
        "Bicubic": Image.Resampling.BICUBIC,
        "Lanczos": Image.Resampling.LANCZOS,
        # Could add the 'Box' filter too, maybe later.
        # "Box": Image.Resampling.BOX
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files: list[str] = []
        self.output_directory: str | None = None
        # Make sure this expects the *resizing* worker.
        self.worker: ImageResizingWorker | None = None
        self.file_path_to_item_map: dict[str, QListWidgetItem] = {}
        self.success_count = 0
        self.fail_count = 0

        # Layout boxes.
        main_layout = QVBoxLayout(self)
        top_controls_layout = QHBoxLayout()
        list_layout = QHBoxLayout()
        options_layout = QHBoxLayout()
        output_dir_layout = QHBoxLayout()
        action_layout = QHBoxLayout()

        # Buttons, lists, inputs...
        # Top buttons: Select, Clear.
        self.select_files_button = QPushButton("Select Image(s)")
        self.select_files_button.setToolTip("Select one or more image files to resize")
        self.clear_list_button = QPushButton("Clear List")
        self.clear_list_button.setToolTip("Remove all selected images from the list")
        top_controls_layout.addWidget(self.select_files_button)
        top_controls_layout.addWidget(self.clear_list_button)
        top_controls_layout.addStretch()

        # List of files to resize.
        self.file_list_widget = QListWidget()
        self.file_list_widget.setToolTip("List of images selected for resizing")
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_layout.addWidget(self.file_list_widget)

        # Box holding all the size and filter options.
        options_frame = QFrame()
        options_frame.setFrameShape(QFrame.Shape.StyledPanel)
        # Stack the size and filter rows vertically inside the frame.
        options_grid_layout = QVBoxLayout(options_frame)

        size_layout = QHBoxLayout()
        filter_layout = QHBoxLayout()

        # Where they type the new width and height.
        width_label = QLabel("Width:")
        self.width_spinbox = QSpinBox()
        self.width_spinbox.setToolTip("Set the target width in pixels")
        self.width_spinbox.setRange(1, 99999)
        self.width_spinbox.setSuffix(" px")
        # Start with some reasonable numbers.
        self.width_spinbox.setValue(800)

        height_label = QLabel("Height:")
        self.height_spinbox = QSpinBox()
        self.height_spinbox.setToolTip("Set the target height in pixels")
        self.height_spinbox.setRange(1, 99999)
        self.height_spinbox.setSuffix(" px")
        # Start with some reasonable numbers.
        self.height_spinbox.setValue(600)

        self.aspect_checkbox = QCheckBox("Maintain Aspect Ratio")
        self.aspect_checkbox.setToolTip("Check to preserve the original image proportions during resize")
        self.aspect_checkbox.setChecked(True)

        size_layout.addWidget(width_label)
        size_layout.addWidget(self.width_spinbox)
        size_layout.addWidget(height_label)
        size_layout.addWidget(self.height_spinbox)
        size_layout.addWidget(self.aspect_checkbox)
        size_layout.addStretch()

        # Dropdown to pick *how* to resize (smooth, sharp, etc.).
        filter_label = QLabel("Filter:")
        self.filter_combo = QComboBox()
        self.filter_combo.setToolTip("Choose the algorithm used for resampling (affects quality and sharpness)")
        self.filter_combo.addItems(list(self.RESAMPLE_FILTERS.keys()))
        # Start with Lanczos, it usually looks good.
        self.filter_combo.setCurrentText("Lanczos")

        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_combo)
        filter_layout.addStretch()

        options_grid_layout.addLayout(size_layout)
        options_grid_layout.addLayout(filter_layout)
        options_layout.addWidget(options_frame)

        # Where to save the resized pics.
        self.output_dir_button = QPushButton("Select Output Folder")
        self.output_dir_button.setToolTip("Choose folder for resized images (Optional: saves in original folder if empty)")
        self.output_dir_label = QLineEdit()
        self.output_dir_label.setPlaceholderText("Select output folder (saves in place if empty)")
        self.output_dir_label.setReadOnly(True)
        self.output_dir_label.setToolTip("Displays the selected output folder path (if any)")
        output_dir_layout.addWidget(self.output_dir_button)
        output_dir_layout.addWidget(self.output_dir_label, 1)

        # Resize button and progress bar.
        self.resize_button = QPushButton("Resize")
        self.resize_button.setToolTip("Start resizing the selected images to the specified dimensions")
        self.resize_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip("Shows the progress of the resizing process")
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setMinimum(0)

        action_layout.addWidget(self.progress_bar, 1)
        action_layout.addWidget(self.resize_button)

        # Putting it all together.
        main_layout.addLayout(top_controls_layout)
        main_layout.addLayout(list_layout)
        main_layout.addLayout(options_layout)
        main_layout.addLayout(output_dir_layout)
        main_layout.addLayout(action_layout)
        self.setLayout(main_layout)

        # Wiring things up.
        self.select_files_button.clicked.connect(self._select_files)
        self.clear_list_button.clicked.connect(self._clear_list)
        self.output_dir_button.clicked.connect(self._select_output_dir)
        # Make the button start the resizing.
        self.resize_button.clicked.connect(self._start_resizing)

    def _update_resize_button_state(self):
        """Enables the resize button only if files are selected."""
        enabled = bool(self.selected_files) and (not self.worker or not self.worker.isRunning())
        self.resize_button.setEnabled(enabled)
        # Gray out options while working.
        processing = self.worker is not None and self.worker.isRunning()
        self.select_files_button.setEnabled(not processing)
        self.clear_list_button.setEnabled(bool(self.selected_files) and not processing)
        self.output_dir_button.setEnabled(not processing)
        self.width_spinbox.setEnabled(not processing)
        self.height_spinbox.setEnabled(not processing)
        self.aspect_checkbox.setEnabled(not processing)
        self.filter_combo.setEnabled(not processing)

    @Slot()
    def _select_files(self):
        image_filter = "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
        files = open_files_dialog(self, "Select Images to Resize", filter=image_filter)
        if files:
            new_files = [f for f in files if f not in self.file_path_to_item_map]
            self.selected_files.extend(new_files)
            for file_path in new_files:
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                item.setToolTip(file_path)
                self.file_list_widget.addItem(item)
                self.file_path_to_item_map[file_path] = item
            self._update_resize_button_state()

    @Slot()
    def _clear_list(self):
        self.selected_files.clear()
        self.file_list_widget.clear()
        self.file_path_to_item_map.clear()
        self._update_resize_button_state()

    @Slot()
    def _select_output_dir(self):
        directory = select_directory_dialog(self, "Select Output Folder (Optional)")
        if directory:
            self.output_directory = directory
            self.output_dir_label.setText(directory)
        else:
            self.output_directory = None
            self.output_dir_label.setText("")
            self.output_dir_label.setPlaceholderText("Select output folder (saves in place if empty)")
        # Output folder doesn't affect if the Resize button is clickable.

    @Slot()
    def _start_resizing(self):
        """Starts the image resizing process."""
        if not self.selected_files:
            QMessageBox.warning(self, "Input Missing", "Please select images to resize.")
            return

        width = self.width_spinbox.value()
        height = self.height_spinbox.value()
        keep_aspect = self.aspect_checkbox.isChecked()
        filter_name = self.filter_combo.currentText()
        # If the filter name is weird, just use Lanczos.
        resample_filter = self.RESAMPLE_FILTERS.get(filter_name, Image.Resampling.LANCZOS)

        if width <= 0 or height <= 0:
             QMessageBox.warning(self, "Invalid Size", "Width and Height must be positive numbers.")
             return

        # Zero out the success/fail counts.
        self.success_count = 0
        self.fail_count = 0
        for item in self.file_path_to_item_map.values():
            item.setForeground(QColor("white"))
            item.setToolTip(item.data(Qt.ItemDataRole.UserRole))

        # Show progress bar, gray out buttons.
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setFormat("Resizing... %v/%m")
        self.progress_bar.setVisible(True)
        # This function handles graying out stuff.
        self._update_resize_button_state()

        # Create and start the worker
        self.worker = ImageResizingWorker(
            self.selected_files, self.output_directory,
            width, height, keep_aspect, resample_filter
        )
        self.worker.progress.connect(self._update_progress)
        self.worker.file_processed.connect(self._handle_file_result)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    @Slot(int, int)
    def _update_progress(self, value: int, total: int):
        """Updates the progress bar."""
        self.progress_bar.setValue(value)
        self.progress_bar.setMaximum(total)

    @Slot(str, str)
    def _handle_file_result(self, original_path: str, status: str):
        """Updates the list item based on the processing status."""
        item = self.file_path_to_item_map.get(original_path)
        if item:
            base_tooltip = item.data(Qt.ItemDataRole.UserRole)
            if status.startswith("Success"):
                item.setForeground(QColor("lightgreen"))
                # Put the result (Success/Error) in the tooltip.
                item.setToolTip(f"{base_tooltip}\nStatus: {status}")
                self.success_count += 1
            elif status == "Cancelled":
                 item.setForeground(QColor("orange"))
                 item.setToolTip(f"{base_tooltip}\nStatus: Cancelled")
            else: # If something went wrong.
                item.setForeground(QColor("red"))
                item.setToolTip(f"{base_tooltip}\nStatus: {status}")
                self.fail_count += 1

    @Slot(str)
    def _handle_error(self, error_message: str):
        """Handles general errors reported by the worker."""
        QMessageBox.critical(self, "Resizing Error", f"Error: {error_message}")
        # The main cleanup runs when the worker finishes.

    @Slot()
    def _on_worker_finished(self):
        """Cleans up after the worker thread finishes."""
        self.progress_bar.setVisible(False)
        # Let go of the worker.
        self.worker = None
        self._update_resize_button_state() # Re-enable buttons

        # Pop-up summary.
        if self.fail_count > 0:
            QMessageBox.warning(self, "Resizing Complete",
                                f"Finished resizing. {self.success_count} succeeded, {self.fail_count} failed.")
        else:
            QMessageBox.information(self, "Resizing Complete",
                                  f"Finished resizing {self.success_count} image(s) successfully.")

# Standalone execution for testing
if __name__ == '__main__':
    # Add necessary imports for standalone execution
    import sys
    import os
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # Adjust path assuming this script is in src/widgets
    style_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'styles.qss')
    try:
        with open(style_path, "r") as f:
            style = f.read()
            app.setStyleSheet(style)
    except FileNotFoundError:
        print(f"Standalone: styles.qss not found at {style_path}.")

    widget = ResizerWidget()
    widget.setGeometry(100, 100, 600, 500)
    widget.show()
    sys.exit(app.exec()) 