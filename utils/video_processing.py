from PySide6.QtCore import QThread, Signal
import subprocess
import os
import traceback
import shlex # For safe command construction
import sys # Needed for sys.frozen and sys._MEIPASS
import shutil # Keep for fallback PATH check

def get_ffmpeg_path() -> str | None:
    """Gets the path to the ffmpeg executable, preferring bundled first."""
    ffmpeg_name = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
    
    if getattr(sys, 'frozen', False):
        # We are running in a PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            # One-file bundle: look in temporary MEIPASS dir
            base_path = sys._MEIPASS
        else:
            # One-folder bundle: look in the executable's directory
            base_path = os.path.dirname(sys.executable)
        
        bundled_path = os.path.join(base_path, ffmpeg_name)
        if os.path.exists(bundled_path):
            print(f"Using bundled FFmpeg: {bundled_path}")
            return bundled_path
        else:
            print(f"Warning: Running bundled, but {ffmpeg_name} not found at {bundled_path}")
            # Fall through to check PATH as a backup even if bundled

    # If not bundled, or bundled check failed, try finding it in PATH
    path_ffmpeg = shutil.which(ffmpeg_name)
    if path_ffmpeg:
        print(f"Using FFmpeg from PATH: {path_ffmpeg}")
        return path_ffmpeg

    print("Error: FFmpeg executable not found (neither bundled nor in system PATH).")
    return None

class VideoCompressionWorker(QThread):
    """Worker thread for compressing video using ffmpeg."""
    # Signals
    # Signal: 'Hey, ffmpeg just started!'
    started = Signal()
    # Signal: 'Done! Here's what happened: Success/Error...'
    # Making my own 'finished' signal 'cause the default one can't carry my status message.
    finished = Signal(str)
    # Signal: 'Whoops, error *before* even starting ffmpeg!'
    error = Signal(str)

    def __init__(self, input_path: str, output_dir: str, crf_value: int, parent=None):
        super().__init__(parent)
        self.input_path = input_path
        self.output_dir = output_dir
        # This CRF thing controls quality. Lower = prettier (and bigger file).
        self.crf_value = crf_value
        self._process: subprocess.Popen | None = None
        # A flag to say 'Stop!', but ffmpeg might ignore me for a bit.
        self._is_running = True

    def run(self):
        # --- Initial Checks --- 
        if not self.input_path or not os.path.exists(self.input_path):
            self.error.emit(f"Input video not found: {self.input_path}")
            self.finished.emit("Error: Input not found") # Need to send the 'finished' signal too, even on error.
            return
        if not self.output_dir:
            self.error.emit("Output directory not specified.")
            self.finished.emit("Error: No output directory") # Need to send the 'finished' signal too, even on error.
            return

        # --- Locate FFmpeg --- 
        ffmpeg_executable = get_ffmpeg_path()
        if not ffmpeg_executable:
             # Error already printed by get_ffmpeg_path
             self.error.emit("FFmpeg executable not found (neither bundled nor in system PATH).")
             self.finished.emit("Error: FFmpeg not found") # Need to send the 'finished' signal too, even on error.
             return

        # --- Prepare Paths and Command --- 
        # Make sure the folder to save in is actually there.
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
            except OSError as e:
                self.error.emit(f"Cannot create output directory: {e}")
                self.finished.emit(f"Error: Cannot create output dir") # Need to send the 'finished' signal too, even on error.
                return

        # Figure out the full path for the output file.
        base_name = os.path.splitext(os.path.basename(self.input_path))[0]
        # Just saving as MP4 for now, maybe let user choose later?
        output_filename = f"{base_name}_compressed.mp4"
        output_path = os.path.join(self.output_dir, output_filename)

        # Building the command line instruction for ffmpeg.
        command = [
            ffmpeg_executable, # Use the located ffmpeg path
            "-y",
            "-hide_banner",
            "-loglevel", "warning", # Changed my mind, let's see warnings too.
            "-i", self.input_path,
            "-c:v", "libx264",
            "-crf", str(self.crf_value),
            "-preset", "medium", # Lots of choices for the speed preset!
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ]

        # --- Execute FFmpeg --- 
        status = "Error: Unknown failure"
        try:
            self.started.emit()
            print(f"Running command: {' '.join(shlex.quote(arg) for arg in command)}")

            # Start the ffmpeg process
            # On Windows, this stops that annoying black box from flashing up.
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            # Run ffmpeg, watch its error messages, ignore normal output.
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE, # Could just throw away the normal output entirely.
                stderr=subprocess.PIPE,
                text=True,
                startupinfo=startupinfo
            )

            # Wait for ffmpeg to finish and grab any messages it printed.
            stdout, stderr = self._process.communicate()
            return_code = self._process.returncode
            # Okay, ffmpeg is done (or crashed).
            self._process = None

            # --- Handle Results --- 
            if not self._is_running:
                 status = "Cancelled"
                 # If cancelled, try to delete the half-finished file.
                 if os.path.exists(output_path):
                     try: os.remove(output_path)
                     except OSError: pass
            elif return_code == 0:
                # Even if ffmpeg says it worked (code 0), check if it printed any warnings.
                if "Error" in stderr or "failed" in stderr.lower():
                     # Just show the last chunk of the error message.
                     status = f"Error: FFmpeg reported issues.\nDetails:\n{stderr[-500:]}"
                else:
                     status = f"Success ({output_filename})"
            else:
                # Something went wrong!
                # Show the end of the error message.
                status = f"Error: FFmpeg failed (code {return_code}).\nDetails:\n{stderr[-500:]}"

        # --- Handle Exceptions --- 
        except FileNotFoundError:
            # This specific error shouldn't happen for ffmpeg_executable itself
            # because we checked its existence in get_ffmpeg_path(), but could 
            # happen if paths in command args are somehow invalid later.
            # The error is more likely caught if get_ffmpeg_path returns None.
            status = f"Error: A file required by FFmpeg was not found."
            print(f"Video Compression FileNotFoundError: {traceback.format_exc()}")
            self.error.emit(status)
        except Exception as e:
            status = f"Error: Failed to run ffmpeg: {e}"
            print(f"Video Compression Error: {traceback.format_exc()}")
            self.error.emit(status)
        finally:
            # --- Final Signal Emission --- 
             if self._is_running:
                self.finished.emit(status)
             else:
                 # Make sure to send 'finished' even when cancelled.
                 self.finished.emit("Cancelled")

    def stop(self):
        """Attempts to terminate the running ffmpeg process."""
        self._is_running = False
        # Is there an ffmpeg process and is it still running?
        if self._process and self._process.poll() is None:
            print("Terminating ffmpeg process...")
            try:
                # Try to tell ffmpeg to stop nicely.
                self._process.terminate()
                try:
                    # Give it a couple seconds to comply.
                    self._process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # It didn't listen, time for the hammer!
                    print("FFmpeg did not terminate gracefully, killing...")
                    # Pull the plug!
                    self._process.kill()
            except Exception as e:
                print(f"Error terminating ffmpeg: {e}")
        # The main part of the code will handle sending the 'Cancelled' signal. 