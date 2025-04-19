import sys
import os
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QComboBox, QLineEdit, QProgressBar, QMessageBox, QListWidgetItem,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QColor # For indicating status in list

# okay we’re gonna try importing some helper functions like civilized folks
# but if they ain't there... we panic (but politely)
try:
    # full-grown imports only. no baby relatives.
    from utils.helpers import open_files_dialog, select_directory_dialog
except ImportError as e:
    print(f"ERROR importing helpers: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # fallback plan: pretend the functions exist and just do... absolutely nothing
    def open_files_dialog(*args, **kwargs): return None
    def select_directory_dialog(*args, **kwargs): return None

# summoning the worker class like a digital sorcerer
try:
    # again, grown-up imports please
    from utils.image_processing import ImageConversionWorker
except ImportError as e:
    print(f"ERROR importing ImageConversionWorker: {e}. Ensure Pixleon root is in PYTHONPATH or run via main.py.")
    # fake it till we make it – this worker does literally nothing
    class ImageConversionWorker(QThread):
        progress = Signal(int, int)
        file_processed = Signal(str, str)
        error = Signal(str)
        def __init__(self, *args, **kwargs): super().__init__()
        def run(self): self.error.emit("Worker not loaded!")
        def stop(self): pass

class ConverterWidget(QWidget):
    SUPPORTED_FORMATS = {
        "JPEG": "jpg",
        "PNG": "png",
        "WEBP": "webp",
        "GIF": "gif",
        "BMP": "bmp",
        "TIFF": "tiff",
        # we can add more if our hearts desire and Pillow agrees
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_files: list[str] = []
        self.output_directory: str | None = None
        self.worker: ImageConversionWorker | None = None
        self.file_path_to_item_map: dict[str, QListWidgetItem] = {}
        self.success_count = 0
        self.fail_count = 0

        # --- Layouts ---
        main_layout = QVBoxLayout(self)
        top_controls_layout = QHBoxLayout()
        list_layout = QHBoxLayout() # this lil layout holds the sacred scroll of files
        format_layout = QHBoxLayout()
        output_dir_layout = QHBoxLayout()
        action_layout = QHBoxLayout()

        # --- Widgets ---
        # buttons up top, feelin' important
        self.select_files_button = QPushButton("Select Image(s)")
        self.select_files_button.setToolTip("Select one or more image files to convert")
        self.clear_list_button = QPushButton("Clear List")
        self.clear_list_button.setToolTip("Remove all selected images from the list")
        top_controls_layout.addWidget(self.select_files_button)
        top_controls_layout.addWidget(self.clear_list_button)
        top_controls_layout.addStretch() # dramatic spacing

        # where the chosen ones (files) are displayed
        self.file_list_widget = QListWidget()
        self.file_list_widget.setToolTip("List of images selected for conversion")
        self.file_list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        list_layout.addWidget(self.file_list_widget)

        # convert what to what tho??
        format_label = QLabel("Convert to:")
        self.format_combo = QComboBox()
        self.format_combo.setToolTip("Choose the target image format for conversion")
        self.format_combo.addItems(list(self.SUPPORTED_FORMATS.keys()))
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        format_layout.addStretch() # for vibes

        # where do we throw the new shiny images?
        self.output_dir_button = QPushButton("Select Output Folder")
        self.output_dir_button.setToolTip("Choose the folder where converted images will be saved")
        self.output_dir_label = QLineEdit()
        self.output_dir_label.setPlaceholderText("Select output folder...")
        self.output_dir_label.setReadOnly(True)
        self.output_dir_label.setToolTip("Displays the selected output folder path")
        output_dir_layout.addWidget(self.output_dir_button)
        output_dir_layout.addWidget(self.output_dir_label, 1)

        # time for action. also progress. and maybe snacks
        self.convert_button = QPushButton("Convert")
        self.convert_button.setToolTip("Start converting the selected images to the chosen format")
        self.convert_button.setEnabled(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setToolTip("Shows the progress of the conversion process")
        self.progress_bar.setVisible(False) # shh... it's a secret unless we're converting
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar.setMinimum(0)

        action_layout.addWidget(self.progress_bar, 1)
        action_layout.addWidget(self.convert_button)

        # --- Final glorious stacking of the layout ---
        main_layout.addLayout(top_controls_layout)
        main_layout.addLayout(list_layout)
        main_layout.addLayout(format_layout)
        main_layout.addLayout(output_dir_layout)
        main_layout.addLayout(action_layout)
        self.setLayout(main_layout)

        # --- Plug it all in ---
        self.select_files_button.clicked.connect(self._select_files)
        self.clear_list_button.clicked.connect(self._clear_list)
        self.output_dir_button.clicked.connect(self._select_output_dir)
        self.convert_button.clicked.connect(self._start_conversion) # let's gooo

    def _update_convert_button_state(self):
        """makes sure we ain't converting air or saving into a void"""
        enabled = bool(self.selected_files) and bool(self.output_directory) and (not self.worker or not self.worker.isRunning())
        self.convert_button.setEnabled(enabled)
        self.select_files_button.setEnabled(not self.worker or not self.worker.isRunning())
        self.clear_list_button.setEnabled(bool(self.selected_files) and (not self.worker or not self.worker.isRunning()))
        self.output_dir_button.setEnabled(not self.worker or not self.worker.isRunning())
        self.format_combo.setEnabled(not self.worker or not self.worker.isRunning())

    @Slot()
    def _select_files(self):
        image_filter = "Images (*.png *.jpg *.jpeg *.bmp *.webp *.gif *.tiff)"
        files = open_files_dialog(self, "Select Images to Convert", filter=image_filter)
        if files:
            # let’s not invite the same file to the party twice
            new_files = [f for f in files if f not in self.file_path_to_item_map]
            self.selected_files.extend(new_files)
            for file_path in new_files:
                item = QListWidgetItem(os.path.basename(file_path))
                item.setData(Qt.ItemDataRole.UserRole, file_path) # sneakily stash full path
                item.setToolTip(file_path) # in case someone wants to snoop
                self.file_list_widget.addItem(item)
                self.file_path_to_item_map[file_path] = item # like a file guest list
            self._update_convert_button_state()

    @Slot()
    def _clear_list(self):
        self.selected_files.clear()
        self.file_list_widget.clear()
        self.file_path_to_item_map.clear()
        self._update_convert_button_state() # reset that glorious convert button

    @Slot()
    def _select_output_dir(self):
        directory = select_directory_dialog(self, "Select Output Folder")
        if directory:
            self.output_directory = directory
            self.output_dir_label.setText(directory)
            self._update_convert_button_state()

    @Slot()
    def _start_conversion(self):
        """and the magic begins 🪄"""
        if not self.selected_files or not self.output_directory:
            QMessageBox.warning(self, "Input Missing", "Please select images and an output folder.")
            return

        selected_format_key = self.format_combo.currentText()
        target_format_ext = self.SUPPORTED_FORMATS.get(selected_format_key)

        if not target_format_ext:
            QMessageBox.critical(self, "Error", "Invalid target format selected.")
            return

        # start fresh like it’s New Year’s Day
        self.success_count = 0
        self.fail_count = 0
        for item in self.file_path_to_item_map.values():
            item.setForeground(QColor("white")) # bless it with innocence
            item.setToolTip(item.data(Qt.ItemDataRole.UserRole)) # restore original info

        # let the UI know we are now in Serious Mode
        self._update_convert_button_state()
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(self.selected_files))
        self.progress_bar.setFormat("Converting... %v/%m")
        self.progress_bar.setVisible(True)

        # summon the worker and set it loose
        self.worker = ImageConversionWorker(self.selected_files, self.output_directory, target_format_ext)
        self.worker.progress.connect(self._update_progress)
        self.worker.file_processed.connect(self._handle_file_result)
        self.worker.error.connect(self._handle_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    @Slot(int, int)
    def _update_progress(self, value: int, total: int):
        """tick tick tick... progress goes brrr"""
        self.progress_bar.setValue(value)
        self.progress_bar.setMaximum(total)

    @Slot(str, str)
    def _handle_file_result(self, original_path: str, status: str):
        """update each file’s emotional status in the list"""
        item = self.file_path_to_item_map.get(original_path)
        if item:
            base_tooltip = item.data(Qt.ItemDataRole.UserRole)
            if status == "Success":
                item.setForeground(QColor("lightgreen"))
                item.setToolTip(f"{base_tooltip}\nStatus: Success")
                self.success_count += 1
            elif status == "Cancelled":
                item.setForeground(QColor("orange"))
                item.setToolTip(f"{base_tooltip}\nStatus: Cancelled")
                # we don’t count cancelled ones. let them live
            else: # sadge
                item.setForeground(QColor("red"))
                item.setToolTip(f"{base_tooltip}\nStatus: {status}")
                self.fail_count += 1

    @Slot(str)
    def _handle_error(self, error_message: str):
        """when things go boom"""
        QMessageBox.critical(self, "Conversion Error", f"Error: {error_message}")
        # it’ll still clean itself up. we hope.

    @Slot()
    def _on_worker_finished(self):
        """the end. roll credits. cleanup time."""
        self.progress_bar.setVisible(False)
        self.worker = None # bye bye lil thread buddy
        self._update_convert_button_state()

        # let’s do some bragging
        total_processed = self.success_count + self.fail_count
        summary_message = f"Conversion finished.\n\nSuccessfully converted: {self.success_count}"
        if self.fail_count > 0:
            summary_message += f"\nFailed: {self.fail_count}"
        # could add cancelled too if we wanna get fancy

        QMessageBox.information(self, "Conversion Complete", summary_message)

# this whole thing can run on its own if you’re into that sort of thing
if __name__ == '__main__':
    # imports again cuz why not
    import sys
    import os
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    # attempt to look good while doing good
    style_path = os.path.join(os.path.dirname(__file__), '..', 'ui', 'styles.qss')
    try:
        with open(style_path, "r") as f:
            style = f.read()
            app.setStyleSheet(style)
    except FileNotFoundError:
        print(f"Standalone: styles.qss not found at {style_path}.")

    widget = ConverterWidget()
    widget.setGeometry(100, 100, 600, 500)
    widget.show()
    sys.exit(app.exec())