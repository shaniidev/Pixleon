import sys
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSizePolicy,
    QProgressDialog, QMessageBox, QFileDialog # Might not need this one if my helper functions are working.
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PIL import Image
import io
import os

# Let's try to grab those helper functions I made.
try:
    # Gotta import this the official way, no shortcuts!
    from utils.helpers import open_file_dialog, save_file_dialog
except ImportError as e:
    print(f"ERROR importing helpers: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # If I can't find the helpers, make fake ones so it doesn't crash?
    def open_file_dialog(*args, **kwargs): return None
    def save_file_dialog(*args, **kwargs): return None

# Time to get the worker that does the heavy lifting.
try:
    # Again, official import only!
    from utils.image_processing import BackgroundRemovalWorker
except ImportError as e:
    print(f"ERROR importing BackgroundRemovalWorker: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # If the worker's missing, make a fake one that just shows an error.
    class BackgroundRemovalWorker(QThread):
        result_ready = Signal(bytes)
        error = Signal(str)
        def __init__(self, *args, **kwargs): super().__init__()
        def run(self): self.error.emit("Worker not loaded!")
        def stop(self): pass

# This thing is a plain old QWidget.
class BackgroundRemoverWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap: QPixmap | None = None
        # Keep the picture data here after I remove the background.
        self.processed_image_data: bytes | None = None
        self.input_image_path: str | None = None
        self.worker: BackgroundRemovalWorker | None = None
        self.progress_dialog: QProgressDialog | None = None

        # Setting up the boxes to hold everything.
        main_layout = QVBoxLayout(self)
        top_controls_layout = QHBoxLayout()
        image_preview_layout = QHBoxLayout()
        bottom_controls_layout = QHBoxLayout()

        # Making all the buttons and preview areas.
        # Buttons at the top: Select, Remove BG.
        self.select_button = QPushButton("Select Image")
        self.select_button.setToolTip("Select an image file (PNG, JPG, WEBP, etc.)")
        self.remove_bg_button = QPushButton("Remove Background")
        self.remove_bg_button.setToolTip("Process the selected image to remove the background")
        # Can't click this yet, need an image first!
        self.remove_bg_button.setEnabled(False)

        top_controls_layout.addWidget(self.select_button)
        top_controls_layout.addWidget(self.remove_bg_button)
        top_controls_layout.addStretch()

        # The two boxes to show the 'before' and 'after' pics.
        self.original_view = QGraphicsView()
        self.original_view.setToolTip("Preview of the original selected image")
        self.processed_view = QGraphicsView()
        self.processed_view.setToolTip("Preview of the image after background removal")
        self.original_scene = QGraphicsScene()
        self.processed_scene = QGraphicsScene()
        self.original_view.setScene(self.original_scene)
        self.processed_view.setScene(self.processed_scene)
        self.original_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.processed_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Put little titles above the preview boxes.
        original_label = QLabel("Original Image")
        processed_label = QLabel("Processed Image")
        original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        processed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        original_container = QVBoxLayout()
        original_container.addWidget(original_label)
        original_container.addWidget(self.original_view)
        processed_container = QVBoxLayout()
        processed_container.addWidget(processed_label)
        processed_container.addWidget(self.processed_view)

        image_preview_layout.addLayout(original_container)
        image_preview_layout.addLayout(processed_container)

        # Button at the bottom: Save.
        self.save_button = QPushButton("Save Image")
        self.save_button.setToolTip("Save the processed image (with transparent background) as a PNG file")
        # Can't save until the background is gone!
        self.save_button.setEnabled(False)
        bottom_controls_layout.addStretch()
        bottom_controls_layout.addWidget(self.save_button)

        # Putting all the layout boxes together.
        main_layout.addLayout(top_controls_layout)
        main_layout.addLayout(image_preview_layout)
        main_layout.addLayout(bottom_controls_layout)
        self.setLayout(main_layout)

        # Hooking up the buttons to the code that makes them work.
        self.select_button.clicked.connect(self._select_image)
        # Make this button actually *do* the thing.
        self.remove_bg_button.clicked.connect(self._remove_background)
        # Make this button actually *do* the thing.
        self.save_button.clicked.connect(self._save_image)

    @Slot()
    def _select_image(self):
        """Opens a file dialog to select an image."""
        image_filter = "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        file_path = open_file_dialog(self, "Select Image File", filter=image_filter)

        if file_path:
            self.input_image_path = file_path
            self.original_pixmap = QPixmap(file_path)
            if self.original_pixmap.isNull():
                QMessageBox.warning(self, "Load Error", f"Could not load image: {file_path}")
                self._reset_views()
                return

            self._display_image(self.original_scene, self.original_pixmap)
            # Get rid of the old 'after' picture if they load a new 'before' one.
            self.processed_scene.clear()
            self.processed_image_data = None
            self.remove_bg_button.setEnabled(True)
            self.save_button.setEnabled(False)
            # Make the picture fit nicely in its box.
            self.original_view.fitInView(self.original_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        else:
            # If they hit Cancel in the file picker, just do nothing.
            pass

    def _display_image(self, scene: QGraphicsScene, pixmap: QPixmap):
        """Clears the scene and displays the pixmap, fitting the view."""
        # Wipe the box clean before putting a new picture in.
        scene.clear()
        item = QGraphicsPixmapItem(pixmap)
        scene.addItem(item)
        # Fit view (assuming view is already linked to scene)
        # Find the box that's supposed to show this picture.
        view = scene.views()[0]
        view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _reset_views(self):
        """Clears image previews and resets button states."""
        self.original_scene.clear()
        self.processed_scene.clear()
        self.original_pixmap = None
        self.processed_image_data = None
        self.input_image_path = None
        self.remove_bg_button.setEnabled(False)
        self.save_button.setEnabled(False)

    @Slot()
    def _remove_background(self):
        """Starts the background removal process in a worker thread."""
        if not self.input_image_path:
            QMessageBox.warning(self, "No Image", "Please select an image first.")
            return

        if self.worker and self.worker.isRunning():
             # Whoa there, don't start another removal if one's already going!
             QMessageBox.information(self, "In Progress", "Background removal is already running.")
             return

        # Gray out the buttons while I'm working.
        self._set_buttons_enabled(False)

        # Make the background remover worker and tell it to GO!
        self.worker = BackgroundRemovalWorker(self.input_image_path)
        self.worker.result_ready.connect(self._handle_result)
        self.worker.error.connect(self._handle_error)
        # Tidy up after the worker is finished.
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

        # Pop up that little 'Working...' box.
        self.progress_dialog = QProgressDialog("Removing background...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setWindowTitle("Processing")
        # This tool doesn't tell me how far along it is, so the progress bar just spins.
        # Make the Cancel button actually do something.
        self.progress_dialog.canceled.connect(self._cancel_processing)
        self.progress_dialog.show()

    @Slot(bytes)
    def _handle_result(self, image_data: bytes):
        """Handles the successful result from the worker."""
        self.processed_image_data = image_data

        # Turn the image data from the worker back into a picture I can show.
        processed_pixmap = QPixmap()
        if not processed_pixmap.loadFromData(image_data):
             self._handle_error("Failed to load processed image data into QPixmap.")
             return

        self._display_image(self.processed_scene, processed_pixmap)
        self.processed_view.fitInView(self.processed_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.save_button.setEnabled(True)

        # Don't need to close the progress box here, it'll close itself later.

    @Slot(str)
    def _handle_error(self, error_message: str):
        """Handles errors reported by the worker."""
        if self.progress_dialog:
            self.progress_dialog.close()
        QMessageBox.critical(self, "Processing Error", f"Error: {error_message}")
        # The buttons will get turned back on when the worker is totally finished.

    @Slot()
    def _on_worker_finished(self):
        """Cleans up after the worker thread finishes."""
        if self.progress_dialog:
            self.progress_dialog.close()
            # Let go of the progress box so memory can be freed.
            self.progress_dialog = None

        # Turn the buttons back on (carefully, only enable if it makes sense!).
        self.select_button.setEnabled(True)
        self.remove_bg_button.setEnabled(self.input_image_path is not None)
        # The save button gets enabled when the result is ready, not here.

        # Let go of the worker so memory can be freed.
        self.worker = None

    @Slot()
    def _cancel_processing(self):
        """Attempts to stop the worker thread if cancel is clicked."""
        if self.worker and self.worker.isRunning():
            print("Attempting to cancel background removal...")
            # Tell the worker thread, 'Hey, stop what you're doing!'
            self.worker.stop()
            # It might not stop instantly, but it'll clean up eventually.
        if self.progress_dialog:
             self.progress_dialog.close()

    @Slot()
    def _save_image(self):
        """Saves the processed image to a file."""
        if not self.processed_image_data:
            QMessageBox.warning(self, "No Image", "No processed image available to save.")
            return

        # Let's guess a good filename, like 'my_pic_nobg.png'.
        default_name = "output_nobg.png"
        if self.input_image_path:
            base, _ = os.path.splitext(os.path.basename(self.input_image_path))
            default_name = f"{base}_nobg.png"

        save_filter = "PNG Image (*.png)"
        save_path = save_file_dialog(self, "Save Processed Image", default_name, save_filter)

        if save_path:
            try:
                with open(save_path, 'wb') as f:
                    f.write(self.processed_image_data)
                QMessageBox.information(self, "Success", f"Image saved successfully to {save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save image: {e}")

    # Little functions just for this widget.
    def _set_buttons_enabled(self, enabled: bool):
        """Helper to enable/disable processing-related buttons."""
        self.select_button.setEnabled(enabled)
        self.remove_bg_button.setEnabled(enabled and self.input_image_path is not None)
        # Save button state depends on processed data, not just this flag
        # self.save_button.setEnabled(enabled and self.processed_image_data is not None)

    # Code to make sure the pictures resize nicely when the window does.
    def resizeEvent(self, event):
        """Handle widget resize events to refit the image views."""
        super().resizeEvent(event) # Call base class implementation
        # When the whole widget resizes, make the pictures fit again.
        self._fit_views()

    def _fit_views(self):
        """Fits the content of both QGraphicsView widgets."""
        # If there are pictures, make 'em fit.
        if not self.original_scene.items():
            # If no original image, clear processed view too
            if not self.processed_scene.items(): return # Nothing to fit
        if self.original_pixmap:
            self.original_view.fitInView(self.original_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        if self.processed_image_data:
            # Need to check if processed_scene has items, as data might exist but pixmap failed load
            if self.processed_scene.items():
                 self.processed_view.fitInView(self.processed_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

# Example of how to run this widget standalone for testing (optional)
if __name__ == '__main__':
    # Add necessary imports for standalone execution
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # Need to load styles if running standalone
    # Adjust path assuming this script is in src/widgets
    style_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'styles.qss')
    try:
        with open(style_path, "r") as f:
            style = f.read()
            app.setStyleSheet(style)
    except FileNotFoundError:
        print(f"Standalone: styles.qss not found at {style_path}.")

    widget = BackgroundRemoverWidget()
    widget.setGeometry(100, 100, 800, 600)
    widget.show()
    sys.exit(app.exec()) 