import sys
import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QLineEdit, QProgressBar, QMessageBox, QListWidgetItem, QSizePolicy,
    QSlider, QSpinBox # Stuff for setting the compression quality.
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor

# Grabbing my helper functions again.
try:
    # Import the proper way!
    from utils.helpers import open_files_dialog, select_directory_dialog
except ImportError as e:
    print(f"ERROR importing helpers: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    def open_files_dialog(*args, **kwargs): return None
    def select_directory_dialog(*args, **kwargs): return None

# Need the worker that does the actual compressing.
try:
    # Proper import, yes!
    from utils.image_processing import ImageCompressionWorker
except ImportError as e:
    print(f"ERROR importing ImageCompressionWorker: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # Fake worker if the real one is missing.
    class ImageCompressionWorker(QThread):
        progress = Signal(int, int)
        file_processed = Signal(str, str)
        error = Signal(str)
        def __init__(self, *args, **kwargs): super().__init__()
        def run(self): self.error.emit("Worker not loaded!")
        def stop(self): pass

class CompressorWidget(QWidget):
    # Right now, just dealing with JPEG quality. Maybe add PNG stuff later?
    DEFAULT_QUALITY = 85

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files: list[str] = []
        self.output_directory: str | None = None
        self.worker: ImageCompressionWorker | None = None
        self.file_path_to_item_map: dict[str, QListWidgetItem] = {}
        self.success_count = 0
        self.fail_count = 0

        # Boxes to organize everything.
        main_layout = QVBoxLayout(self)
        top_controls_layout = QHBoxLayout()
        list_layout = QHBoxLayout()
        quality_layout = QHBoxLayout()
        output_dir_layout = QHBoxLayout()
        action_layout = QHBoxLayout()

        # All the buttons, lists, sliders, etc.
        # Buttons at the very top.
        self.select_files_button = QPushButton("Select Image(s)")
        self.select_files_button.setToolTip("Select one or more image files to compress")
        self.clear_list_button = QPushButton("Clear List")
        self.clear_list_button.setToolTip("Remove all selected images from the list")
        top_controls_layout.addWidget(self.select_files_button)
        top_controls_layout.addWidget(self.clear_list_button)
        top_controls_layout.addStretch()

        # The box showing all the files you picked.
        self.file_list_widget = QListWidget()
        self.file_list_widget.setToolTip("List of images selected for compression")
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_layout.addWidget(self.file_list_widget)

        # Slider and box for picking JPEG quality.
        quality_label = QLabel("JPEG Quality:")
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setToolTip("Adjust JPEG/WEBP quality (1=Lowest, 100=Highest). Affects file size.")
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(self.DEFAULT_QUALITY)
        self.quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality_slider.setTickInterval(10)

        self.quality_spinbox = QSpinBox()
        self.quality_spinbox.setToolTip("Adjust JPEG/WEBP quality (1=Lowest, 100=Highest). Affects file size.")
        self.quality_spinbox.setRange(1, 100)
        self.quality_spinbox.setValue(self.DEFAULT_QUALITY)
        self.quality_spinbox.setSuffix("%")
        self.quality_spinbox.setFixedWidth(70)

        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_slider, 1)
        quality_layout.addWidget(self.quality_spinbox)
        # Maybe a checkbox for PNG optimization later?

        # Put a little help text under the quality slider.
        info_text = (
            "<b>Tip:</b> <b>JPEG/WEBP</b> offer the smallest size (best for photos), controlled by the quality slider. "
            "<b>PNG</b> uses lossless compression (best quality for graphics/logos), size reduction may be less. "
            "Other formats may not compress significantly."
        )
        self.info_label = QLabel(info_text)
        # Let the text wrap to the next line if it's too long.
        self.info_label.setWordWrap(True)
        # Make this text a bit smaller and grayer.
        self.info_label.setStyleSheet("font-size: 9pt; color: #a0a5b0;")

        # Button and box for choosing where to save files.
        self.output_dir_button = QPushButton("Select Output Folder")
        self.output_dir_button.setToolTip("Choose folder for compressed images (Optional: saves in original folder if empty)")
        self.output_dir_label = QLineEdit()
        self.output_dir_label.setPlaceholderText("Select output folder (saves in place if empty)")
        self.output_dir_label.setReadOnly(True)
        self.output_dir_label.setToolTip("Displays the selected output folder path (if any)")
        output_dir_layout.addWidget(self.output_dir_button)
        output_dir_layout.addWidget(self.output_dir_label, 1)

        # The 'Compress' button and the progress bar.
        self.compress_button = QPushButton("Compress")
        self.compress_button.setToolTip("Start compressing the selected images with the chosen quality")
        self.compress_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip("Shows the progress of the compression process")
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setMinimum(0)

        action_layout.addWidget(self.progress_bar, 1)
        action_layout.addWidget(self.compress_button)

        # Putting all the boxes together.
        main_layout.addLayout(top_controls_layout)
        main_layout.addLayout(list_layout)
        main_layout.addLayout(quality_layout)
        # Stick that help text in the layout.
        main_layout.addWidget(self.info_label)
        main_layout.addLayout(output_dir_layout)
        main_layout.addLayout(action_layout)
        self.setLayout(main_layout)

        # Linking buttons and sliders to their code.
        self.select_files_button.clicked.connect(self._select_files)
        self.clear_list_button.clicked.connect(self._clear_list)
        self.output_dir_button.clicked.connect(self._select_output_dir)
        self.quality_slider.valueChanged.connect(self.quality_spinbox.setValue)
        self.quality_spinbox.valueChanged.connect(self.quality_slider.setValue)
        self.compress_button.clicked.connect(self._start_compression)

    def _update_compress_button_state(self):
        """Enables the compress button only if files are selected."""
        # Don't *need* an output folder, so just check if there are files.
        enabled = bool(self.selected_files) and (not self.worker or not self.worker.isRunning())
        self.compress_button.setEnabled(enabled)
        # Gray out everything else while it's working.
        processing = self.worker is not None and self.worker.isRunning()
        self.select_files_button.setEnabled(not processing)
        self.clear_list_button.setEnabled(bool(self.selected_files) and not processing)
        self.output_dir_button.setEnabled(not processing)
        self.quality_slider.setEnabled(not processing)
        self.quality_spinbox.setEnabled(not processing)

    @Slot()
    def _select_files(self):
        # Only let them pick picture types that make sense to compress.
        image_filter = "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
        files = open_files_dialog(self, "Select Images to Compress", filter=image_filter)
        if files:
            new_files = [f for f in files if f not in self.file_path_to_item_map]
            self.selected_files.extend(new_files)
            for file_path in new_files:
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                item.setToolTip(file_path)
                self.file_list_widget.addItem(item)
                self.file_path_to_item_map[file_path] = item
            self._update_compress_button_state()

    @Slot()
    def _clear_list(self):
        self.selected_files.clear()
        self.file_list_widget.clear()
        self.file_path_to_item_map.clear()
        self._update_compress_button_state()

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
        # Changing the output folder doesn't affect whether the Compress button is enabled.

    @Slot()
    def _start_compression(self):
        """Starts the image compression process."""
        if not self.selected_files:
            QMessageBox.warning(self, "Input Missing", "Please select images to compress.")
            return

        quality = self.quality_spinbox.value()

        # Set success/fail counts back to zero.
        self.success_count = 0
        self.fail_count = 0
        for item in self.file_path_to_item_map.values():
            # Make the text color normal again.
            item.setForeground(QColor("white"))
            # Put the hint back to just showing the file path.
            item.setToolTip(item.data(Qt.ItemDataRole.UserRole))

        # Gray out stuff and show the progress bar.
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setFormat("Compressing... %v/%m")
        self.progress_bar.setVisible(True)
        self._update_compress_button_state() # Will disable buttons as worker starts

        # Create and start the worker
        # Give the worker the output folder (or nothing if none was picked).
        self.worker = ImageCompressionWorker(self.selected_files, self.output_directory, quality)
        self.worker.progress.connect(self._update_progress)
        self.worker.file_processed.connect(self._handle_file_result)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

        # Double-check the button states right after the worker starts.
        self._update_compress_button_state()

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
                # Add info about the compression result to the tooltip.
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
        """Handle critical errors from the worker thread."""
        # Catch any big errors from the worker.
        QMessageBox.critical(self, "Compression Error", f"A critical error occurred: {error_message}")
        # Worker finished signal will still be called for cleanup

    @Slot()
    def _on_worker_finished(self):
        """Cleans up after the worker thread finishes."""
        self.progress_bar.setVisible(False)
        self.worker = None # Let go of the worker object.
        self._update_compress_button_state() # Re-enable buttons

        # Pop up a box saying how many files worked/failed.
        if self.fail_count > 0:
            QMessageBox.warning(self, "Compression Complete",
                                f"Finished compressing. {self.success_count} succeeded, {self.fail_count} failed.")
        else:
            QMessageBox.information(self, "Compression Complete",
                                  f"Finished compressing {self.success_count} image(s) successfully.")
        # Should I let them change the output folder now? Maybe not.
        # self.output_dir_button.setEnabled(True)

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

    widget = CompressorWidget()
    widget.setGeometry(100, 100, 600, 500)
    widget.show()
    sys.exit(app.exec()) 