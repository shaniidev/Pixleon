import sys
import os
# Need this to see if ffmpeg is installed.
import shutil
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QMessageBox, QSizePolicy, QSlider, QSpinBox, QFrame # Added the slider and stuff for quality.
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor

# Helpers again!
try:
    # Proper imports!
    from utils.helpers import open_file_dialog, select_directory_dialog
except ImportError as e:
    print(f"ERROR importing helpers: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    def open_file_dialog(*args, **kwargs): return None
    def select_directory_dialog(*args, **kwargs): return None

# The worker for videos.
try:
    # Yep, proper.
    from utils.video_processing import VideoCompressionWorker
except ImportError as e:
    print(f"ERROR importing VideoCompressionWorker: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # Fake one if needed.
    class VideoCompressionWorker(QThread):
        started = Signal()
        finished = Signal(str)
        error = Signal(str)
        def __init__(self, *args, **kwargs): super().__init__()
        def run(self): self.error.emit("Worker not loaded!"); self.finished.emit("Error: Worker not loaded!")
        def stop(self): pass

class VideoCompressorWidget(QWidget):
    # Turning my simple 1-5 quality into the weird CRF number ffmpeg uses. Lower CRF = prettier but bigger!
    # Found this magic formula here.
    # https://trac.ffmpeg.org/wiki/Encode/H.264
    QUALITY_TO_CRF = {
        1: 30, # Ugly but small.
        2: 28,
        3: 25, # Just right?
        4: 23,
        5: 20  # Pretty but chonky.
    }
    # Starting in the middle.
    DEFAULT_QUALITY_LEVEL = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.input_video_path: str | None = None
        self.output_directory: str | None = None
        # Make sure this variable expects a *video* worker.
        self.worker: VideoCompressionWorker | None = None
        self.is_ffmpeg_available = self._check_ffmpeg()

        # Organizing boxes.
        main_layout = QVBoxLayout(self)
        file_select_layout = QHBoxLayout()
        options_layout = QHBoxLayout()
        output_dir_layout = QHBoxLayout()
        action_layout = QHBoxLayout()

        # Gotta check if ffmpeg is even installed first!
        if not self.is_ffmpeg_available:
            error_label = QLabel(
                "<font color='red'>Error: FFmpeg not found in system PATH.</font><br>"
                "Video compression requires FFmpeg to be installed and accessible.<br>"
                "Please install FFmpeg and ensure it's added to your PATH environment variable."
            )
            error_label.setTextFormat(Qt.TextFormat.RichText)
            error_label.setWordWrap(True)
            main_layout.addWidget(error_label)
            # Could just gray everything out if ffmpeg is missing.
            # self.setEnabled(False)
            # Or... just show the warning and let them try anyway?

        # Buttons, labels, sliders...
        # Picking the video file.
        self.select_file_button = QPushButton("Select Video")
        self.select_file_button.setToolTip("Select a video file to compress")
        self.input_file_label = QLineEdit()
        self.input_file_label.setPlaceholderText("Select a video file...")
        self.input_file_label.setReadOnly(True)
        self.input_file_label.setToolTip("Displays the path of the selected input video")
        file_select_layout.addWidget(self.select_file_button)
        file_select_layout.addWidget(self.input_file_label, 1)

        # Quality settings.
        options_frame = QFrame()
        options_frame.setFrameShape(QFrame.Shape.StyledPanel)
        quality_layout = QHBoxLayout(options_frame)

        quality_desc_label = QLabel("Quality (1=Smallest File, 5=Highest Quality):")
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setToolTip("Adjust compression level (lower value = smaller file, lower quality)")
        # Slider goes 1-5, but I'll convert it.
        self.quality_slider.setRange(1, 5)
        self.quality_slider.setValue(self.DEFAULT_QUALITY_LEVEL)
        self.quality_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.quality_slider.setTickInterval(1)

        # Shows the simple 1-5 number.
        self.quality_value_label = QLabel(str(self.DEFAULT_QUALITY_LEVEL))
        self.quality_value_label.setToolTip("Current quality setting (1-5)")
        self.quality_value_label.setFixedWidth(30)
        self.quality_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        quality_layout.addWidget(quality_desc_label)
        quality_layout.addWidget(self.quality_slider, 1)
        quality_layout.addWidget(self.quality_value_label)
        options_layout.addWidget(options_frame)

        # Choosing where to save the compressed video.
        self.output_dir_button = QPushButton("Select Output Folder")
        self.output_dir_button.setToolTip("Choose the folder where the compressed video will be saved")
        self.output_dir_label = QLineEdit()
        self.output_dir_label.setPlaceholderText("Select output folder (required)")
        self.output_dir_label.setReadOnly(True)
        self.output_dir_label.setToolTip("Displays the selected output folder path")
        output_dir_layout.addWidget(self.output_dir_button)
        output_dir_layout.addWidget(self.output_dir_label, 1)

        # The 'Compress' button and the label that says 'Working...' or 'Done!'.
        self.compress_button = QPushButton("Compress Video")
        self.compress_button.setToolTip("Start compressing the video using FFmpeg")
        # Only clickable when you've picked a file AND folder.
        self.compress_button.setEnabled(False)
        # This label shows what's happening.
        self.status_label = QLabel("")
        self.status_label.setToolTip("Shows the current status of the video compression")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        action_layout.addWidget(self.status_label, 1)
        action_layout.addWidget(self.compress_button)

        # Put all the boxes together.
        main_layout.addLayout(file_select_layout)
        main_layout.addLayout(options_layout)
        main_layout.addLayout(output_dir_layout)
        main_layout.addLayout(action_layout)
        # Shove everything upwards.
        main_layout.addStretch()
        self.setLayout(main_layout)

        # If ffmpeg isn't there, disable all the buttons etc (except the error message).
        if not self.is_ffmpeg_available:
             for widget in self.findChildren(QWidget):
                  if widget is not error_label:
                       widget.setEnabled(False)

        # Hooking things up.
        self.select_file_button.clicked.connect(self._select_file)
        self.output_dir_button.clicked.connect(self._select_output_dir)
        self.quality_slider.valueChanged.connect(lambda v: self.quality_value_label.setText(str(v)))
        # Make the compress button do the compression.
        self.compress_button.clicked.connect(self._start_compression)

    def _check_ffmpeg(self) -> bool:
        """Checks if ffmpeg command is available in PATH."""
        return shutil.which("ffmpeg") is not None

    def _update_compress_button_state(self):
        """Enables the compress button only if ffmpeg found, file and output dir selected."""
        is_running = self.worker is not None and self.worker.isRunning()
        enabled = (
            self.is_ffmpeg_available and
            self.input_video_path is not None and
            self.output_directory is not None and
            not is_running
        )
        self.compress_button.setEnabled(enabled)
        # Gray out buttons while ffmpeg is running.
        self.select_file_button.setEnabled(not is_running and self.is_ffmpeg_available)
        self.output_dir_button.setEnabled(not is_running and self.is_ffmpeg_available)
        self.quality_slider.setEnabled(not is_running and self.is_ffmpeg_available)

    @Slot()
    def _select_file(self):
        # Just the usual video types.
        video_filter = "Video Files (*.mp4 *.avi *.mov *.mkv *.webm *.flv)"
        file_path = open_file_dialog(self, "Select Video File", filter=video_filter)
        if file_path:
            self.input_video_path = file_path
            self.input_file_label.setText(file_path)
            # Wipe the status message clean.
            self.status_label.setText("")
            self._update_compress_button_state()

    @Slot()
    def _select_output_dir(self):
        directory = select_directory_dialog(self, "Select Output Folder")
        if directory:
            self.output_directory = directory
            self.output_dir_label.setText(directory)
            self._update_compress_button_state()

    @Slot()
    def _start_compression(self):
        """Starts the video compression process."""
        if not self.input_video_path or not self.output_directory:
            QMessageBox.warning(self, "Input Missing", "Please select an input video and output folder.")
            return

        quality_level = self.quality_slider.value()
        # If the quality number is weird, just use 25 (medium-ish).
        crf_value = self.QUALITY_TO_CRF.get(quality_level, 25)

        # Change the status label to 'Preparing...'.
        self.status_label.setText("Preparing...")
        # This function will gray out the buttons.
        self._update_compress_button_state()

        # Create and start worker
        self.worker = VideoCompressionWorker(self.input_video_path, self.output_directory, crf_value)
        self.worker.started.connect(self._handle_worker_started)
        self.worker.finished.connect(self._handle_worker_finished)
        # Catch errors that happen *before* ffmpeg even starts.
        self.worker.error.connect(self._handle_error)
        # Make sure things get cleaned up even if the worker crashes right away.
        self.worker.finished.connect(self._ensure_cleanup)
        self.worker.start()

        # Just make *really* sure the buttons are disabled.
        self._update_compress_button_state()

    @Slot()
    def _handle_worker_started(self):
        """Called when the ffmpeg process actually starts."""
        self.status_label.setText("Processing... (this may take a while)")
        # The buttons *should* be gray already, but just in case.

    @Slot(str)
    def _handle_worker_finished(self, status: str):
        """Handles the finished signal from the worker (contains status)."""
        if status.startswith("Success"):
            self.status_label.setText(f"<font color='lightgreen'>{status}</font>")
            QMessageBox.information(self, "Compression Complete", f"Video successfully compressed!\n{status}")
        elif status == "Cancelled":
            self.status_label.setText("<font color='orange'>Cancelled</font>")
        else: # If something went wrong.
            self.status_label.setText(f"<font color='red'>{status}</font>")
            QMessageBox.critical(self, "Compression Error", f"Video compression failed.\n\n{status}")

        # Let go of the worker object.
        self.worker = None
        # Turn the buttons back on.
        self._update_compress_button_state()

    @Slot(str)
    def _handle_error(self, error_message: str):
        """Handles errors emitted *before* or *during* worker execution attempt."""
        QMessageBox.critical(self, "Worker Error", error_message)
        self.status_label.setText(f"<font color='red'>Error: {error_message}</font>")
        # Make double sure the worker object is gone.
        self.worker = None
        self._update_compress_button_state()

    @Slot()
    def _ensure_cleanup(self):
        """Connected to QThread.finished to ensure worker reference is cleared."""
        # This cleanup might run *after* the other finish/error handlers.
        # Depending on which signal fired first.
        # It's just here to make absolutely sure cleanup happens.
        if self.worker is not None:
            print("Performing final worker cleanup.")
            self.worker = None
            self._update_compress_button_state() # Ensure buttons re-enabled if error happened early

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

    widget = VideoCompressorWidget()
    widget.setGeometry(100, 100, 600, 300)
    widget.show()
    sys.exit(app.exec()) 