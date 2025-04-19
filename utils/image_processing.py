from PySide6.QtCore import QThread, Signal
from PIL import Image, UnidentifiedImageError
import rembg
import io
import os
# So I can print out the *whole* ugly error message if something breaks.
import traceback

class BackgroundRemovalWorker(QThread):
    """Worker thread for removing image background using rembg."""
    # Signals
    # This signal shouts, 'Hey, I got the picture data (as bytes)!'
    result_ready = Signal(bytes)
    # This signal yells, 'Oops, something broke!', and gives a reason.
    error = Signal(str)
    # This signal just says 'I'm done', whether it worked or not.
    # P.S. QThread already has a 'finished' signal, I can just use that one.
    # Could add a progress signal, but rembg doesn't make it easy.
    # progress = Signal(int)

    def __init__(self, input_path: str, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self._is_running = True

    def run(self):
        """The core logic executed in the separate thread."""
        if not self._is_running:
             # This should never happen... but just in case!
            return

        try:
            # Step 1: Read the picture file.
            with open(self.input_path, 'rb') as i:
                input_data = i.read()

            # Step 2: Tell rembg to do its magic.
            # This part might take a while!
            output_data = rembg.remove(input_data)

            # Step 3: Did someone tell me to stop while I was working?
            if not self._is_running:
                 # If stopped, don't send back the picture.
                 # The 'finished' signal will still go out, though.
                return

            # Step 4: Send the processed picture data back!
            self.result_ready.emit(output_data)

        except FileNotFoundError:
            self.error.emit(f"Error: Input file not found at {self.input_path}")
        except Exception as e:
            # Catch any other weird errors.
            # Get the super detailed error info.
            detailed_error = traceback.format_exc()
            # Print the detailed error for debugging.
            print(f"Background Removal Error: {detailed_error}")
            self.error.emit(f"Failed to remove background: {e}")
        # Remember, QThread sends 'finished' automatically when this function ends.

    def stop(self):
        """Signals the thread to stop processing."""
        self._is_running = False
        # FYI: Can't easily tell rembg to stop halfway through.
        # This 'stop' flag mostly just stops me from sending the result if I finished *after* being told to stop.
        # (Like, between step 2 and step 4).
        # To *really* stop it mid-calculation, I'd need fancier code...
        # ...especially if rembg takes ages on some images.

# --- Worker for Changing Image Formats ---

class ImageConversionWorker(QThread):
    """Worker thread for converting multiple images using Pillow."""
    # Signals
    # Sends: file number I'm on, total files.
    progress = Signal(int, int)
    # Sends: original filename, and 'Success' or an error message.
    file_processed = Signal(str, str)
    # For errors that happen before I even start the loop.
    error = Signal(str)
    # QThread gives me the 'finished' signal for free.

    def __init__(self, input_paths: list[str], output_dir: str, target_format: str, parent=None):
        super().__init__(parent)
        self.input_paths = input_paths
        self.output_dir = output_dir
        # Make sure the format is just 'png', not '.png' or 'PNG'.
        self.target_format = target_format.lower().strip('.')
        self._is_running = True

    def run(self):
        if not self.input_paths:
            self.error.emit("No input files provided.")
            return
        if not self.output_dir:
            self.error.emit("No output directory selected.")
            return
        if not self.target_format:
            self.error.emit("No target format selected.")
            return

        total_files = len(self.input_paths)
        # Send 0% progress right at the start.
        self.progress.emit(0, total_files)

        for i, input_path in enumerate(self.input_paths):
            if not self._is_running:
                 # If told to stop, mark as cancelled and move on (or stop if it's the last file).
                self.file_processed.emit(input_path, "Cancelled")
                continue

            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_filename = f"{base_name}.{self.target_format}"
            output_path = os.path.join(self.output_dir, output_filename)

            status = ""
            try:
                with Image.open(input_path) as img:
                    # Figure out the exact format name Pillow wants.
                    save_format = self.target_format.upper()
                    # Pillow likes 'JPEG', not 'JPG'.
                    if save_format == 'JPG':
                        save_format = 'JPEG'

                    # Handle transparency for JPEG
                    if save_format == 'JPEG':
                        # JPEGs can't have transparency, so convert if needed
                        if img.mode == 'RGBA' or img.mode == 'LA' or 'P' in img.mode:
                             # Convert to RGB, potentially handling palette
                             if 'P' in img.mode:
                                 # If palette has transparency, convert via RGBA
                                 if 'transparency' in img.info:
                                     img = img.convert('RGBA').convert('RGB')
                                 else:
                                     img = img.convert('RGB')
                             else:
                                 img = img.convert('RGB')

                    # Save using the format name Pillow understands.
                    img.save(output_path, format=save_format)
                    status = "Success"
            except FileNotFoundError:
                status = f"Error: File not found"
            except UnidentifiedImageError:
                status = f"Error: Cannot identify image file (corrupted or unsupported format)"
            except Exception as e:
                status = f"Error: {e}"
                detailed_error = traceback.format_exc()
                print(f"Conversion Error for {input_path}: {detailed_error}")

            if self._is_running:
                self.file_processed.emit(input_path, status)
                # Tell the progress bar I finished one more file.
                self.progress.emit(i + 1, total_files)
            else:
                 self.file_processed.emit(input_path, "Cancelled")

        # QThread sends 'finished' when I'm done with the loop.

    def stop(self):
        """Signals the thread to stop processing the list."""
        self._is_running = False

# --- Worker for Making Images Smaller ---

class ImageCompressionWorker(QThread):
    """Worker thread for compressing multiple images using Pillow."""
    # Sends: current file #, total files.
    progress = Signal(int, int)
    # Sends: filename, and status message.
    file_processed = Signal(str, str)
    # For errors before the loop.
    error = Signal(str)

    def __init__(self, input_paths: list[str], output_dir: str | None, quality: int, parent=None):
        super().__init__(parent)
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.quality = quality
        self._is_running = True

    def run(self):
        if not self.input_paths:
            self.error.emit("No input files provided.")
            return

        total_files = len(self.input_paths)
        self.progress.emit(0, total_files)

        for i, input_path in enumerate(self.input_paths):
            if not self._is_running:
                self.file_processed.emit(input_path, "Cancelled")
                continue

            file_dir = os.path.dirname(input_path)
            file_name = os.path.basename(input_path)
            base_name, ext = os.path.splitext(file_name)
            ext = ext.lower()

            # Where should I save? The chosen folder, or the original folder if none was chosen.
            current_output_dir = self.output_dir if self.output_dir else file_dir
            # If the output folder isn't there, try making it.
            if self.output_dir and not os.path.exists(self.output_dir):
                try:
                    os.makedirs(self.output_dir)
                except OSError as e:
                     # If I can't make the folder, skip this file.
                     self.file_processed.emit(input_path, f"Error: Cannot create output dir {self.output_dir}: {e}")
                     self.progress.emit(i + 1, total_files)
                     continue

            # Avoid overwriting original if saving in place
            output_filename = f"{base_name}_compressed{ext}"
            if current_output_dir == file_dir and output_filename == file_name:
                 output_filename = f"{base_name}_compressed_1{ext}" # Simple differentiation

            output_path = os.path.join(current_output_dir, output_filename)

            status = ""
            try:
                with Image.open(input_path) as img:
                    # Set up options like quality or optimization.
                    save_options = {}
                    img_format = img.format
                    # If Pillow doesn't recognize the format, guess based on the filename.
                    if not img_format:
                        # Basic format guessing from extension
                        if ext in ['.jpg', '.jpeg']: img_format = 'JPEG'
                        elif ext == '.png': img_format = 'PNG'
                        elif ext == '.webp': img_format = 'WEBP'
                        elif ext == '.gif': img_format = 'GIF'
                        elif ext == '.bmp': img_format = 'BMP'
                        elif ext == '.tiff': img_format = 'TIFF'
                        else:
                             status = f"Error: Unsupported/Unknown original format ({ext})"
                             raise ValueError(status) # Skip saving if format unknown

                    if img_format == 'JPEG':
                        save_options['quality'] = self.quality
                        save_options['optimize'] = True
                        # JPEGs need RGB format.
                        if img.mode in ['RGBA', 'LA'] or ('P' in img.mode and 'transparency' in img.info):
                            img = img.convert('RGB')
                    elif img_format == 'PNG':
                        save_options['optimize'] = True
                    elif img_format == 'WEBP':
                         save_options['quality'] = self.quality
                         # Handle WEBP transparency conversion if necessary (Pillow usually handles this)

                    img.save(output_path, format=img_format, **save_options)
                    # Add quality level to success message for JPEGs.
                    if img_format in ['JPEG', 'WEBP']:
                         status = f"Success (Q={self.quality})"
                    elif img_format == 'PNG':
                         status = "Success (Optimized)"
                    else:
                         status = "Success"
            except FileNotFoundError:
                status = f"Error: File not found"
            except UnidentifiedImageError:
                status = f"Error: Cannot identify image file"
            except ValueError as ve:
                 status = str(ve) # Use the ValueError message set earlier
            except Exception as e:
                status = f"Error: {e}"
                detailed_error = traceback.format_exc()
                print(f"Compression Error for {input_path}: {detailed_error}")

            if self._is_running:
                self.file_processed.emit(input_path, status)
                self.progress.emit(i + 1, total_files)
            else:
                self.file_processed.emit(input_path, "Cancelled")

    def stop(self):
        self._is_running = False

# --- Worker for Changing Image Size ---

class ImageResizingWorker(QThread):
    """Worker thread for resizing multiple images using Pillow."""
    # Sends: current file #, total files.
    progress = Signal(int, int)
    # Sends: filename, status message.
    file_processed = Signal(str, str)
    # For errors before the loop.
    error = Signal(str)

    def __init__(self, input_paths: list[str], output_dir: str | None,
                 target_width: int, target_height: int, keep_aspect: bool,
                 resample_filter: Image.Resampling, parent=None):
        super().__init__(parent)
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.target_width = target_width
        self.target_height = target_height
        self.keep_aspect = keep_aspect
        self.resample_filter = resample_filter
        self._is_running = True

    def run(self):
        if not self.input_paths:
            self.error.emit("No input files provided.")
            return
        if self.target_width <= 0 or self.target_height <= 0:
            self.error.emit("Target width and height must be positive.")
            return

        total_files = len(self.input_paths)
        self.progress.emit(0, total_files)

        for i, input_path in enumerate(self.input_paths):
            if not self._is_running:
                self.file_processed.emit(input_path, "Cancelled")
                continue

            file_dir = os.path.dirname(input_path)
            file_name = os.path.basename(input_path)
            base_name, ext = os.path.splitext(file_name)
            ext = ext.lower()

            current_output_dir = self.output_dir if self.output_dir else file_dir
            if self.output_dir and not os.path.exists(self.output_dir):
                try:
                    os.makedirs(self.output_dir)
                except OSError as e:
                    self.file_processed.emit(input_path, f"Error: Cannot create output dir {self.output_dir}: {e}")
                    self.progress.emit(i + 1, total_files)
                    continue

            # Suggest a name, avoid simple overwrite if saving in place
            output_filename = f"{base_name}_resized{ext}"
            if current_output_dir == file_dir and output_filename == file_name:
                 output_filename = f"{base_name}_resized_1{ext}"

            output_path = os.path.join(current_output_dir, output_filename)

            status = ""
            try:
                with Image.open(input_path) as img:
                    original_width, original_height = img.size
                    new_width, new_height = self.target_width, self.target_height

                    if self.keep_aspect:
                        width_ratio = self.target_width / original_width
                        height_ratio = self.target_height / original_height
                        # Use the smaller ratio to fit within bounds
                        ratio = min(width_ratio, height_ratio)
                        new_width = int(original_width * ratio)
                        new_height = int(original_height * ratio)
                        # Ensure at least 1 pixel dimension
                        new_width = max(1, new_width)
                        new_height = max(1, new_height)

                    # Resize the image
                    resized_img = img.resize((new_width, new_height), self.resample_filter)

                    # Save in the original format if possible
                    img_format = img.format or ext.lstrip('.').upper()
                    if img_format == 'JPG': img_format = 'JPEG' # Correct identifier
                    # Handle JPEG RGB conversion
                    save_options = {}
                    if img_format == 'JPEG':
                         if resized_img.mode != 'RGB':
                              resized_img = resized_img.convert('RGB')
                         save_options['quality'] = 95 # Default high quality for resize

                    resized_img.save(output_path, format=img_format, **save_options)
                    status = f"Success ({new_width}x{new_height})"

            except FileNotFoundError:
                status = f"Error: File not found"
            except UnidentifiedImageError:
                status = f"Error: Cannot identify image file"
            except Exception as e:
                status = f"Error: {e}"
                detailed_error = traceback.format_exc()
                print(f"Resizing Error for {input_path}: {detailed_error}")

            if self._is_running:
                self.file_processed.emit(input_path, status)
                self.progress.emit(i + 1, total_files)
            else:
                self.file_processed.emit(input_path, "Cancelled")

    def stop(self):
        self._is_running = False

# --- Standalone Test Functions (Optional) ---

# You could add standalone functions here for testing individual operations
# Example (Conceptual):
# def resize_image(input_path: str, output_path: str, width: int, height: int, keep_aspect: bool):
#     try:
#         with Image.open(input_path) as img:
#             # ... (resizing logic from worker) ...
#             img.save(output_path)
#         print(f"Resized {input_path} to {output_path}")
#     except Exception as e:
#         print(f"Error resizing {input_path}: {e}") 