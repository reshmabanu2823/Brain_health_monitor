import os
import sys
import string
import platform
import threading
import time

# ── Detect platform ───────────────────────────────────────────────
IS_WINDOWS = platform.system() == 'Windows'
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif')

def get_usb_drives():
    """Returns list of USB drive paths available on the system."""
    drives = []

    if IS_WINDOWS:
        try:
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i, letter in enumerate(string.ascii_uppercase):
                if bitmask & (1 << i):
                    drive = f"{letter}:\\"
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                    if drive_type == 2:  # DRIVE_REMOVABLE
                        drives.append(drive)
        except Exception as e:
            print(f"[USB] Windows drive detection error: {e}")

    else:
        # Linux / Raspberry Pi
        media_paths = ['/media', '/media/pi', '/mnt']
        for base in media_paths:
            if os.path.exists(base):
                try:
                    for entry in os.listdir(base):
                        full_path = os.path.join(base, entry)
                        if os.path.isdir(full_path) and os.path.ismount(full_path):
                            drives.append(full_path)
                except:
                    pass

    return drives

def get_images_from_drive(drive_path):
    """Scans a drive/folder and returns all MRI image files found."""
    images = []
    try:
        for root, dirs, files in os.walk(drive_path):
            # Skip hidden and system folders
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                if file.lower().endswith(IMAGE_EXTENSIONS):
                    images.append(os.path.join(root, file))
    except Exception as e:
        print(f"[USB] Error scanning drive {drive_path}: {e}")
    return images

class USBMonitor:
    """Monitors for USB drive insertion and removal in background thread."""

    def __init__(self, on_drive_inserted=None, on_drive_removed=None):
        self.on_drive_inserted = on_drive_inserted
        self.on_drive_removed  = on_drive_removed
        self._known_drives     = set(get_usb_drives())
        self._running          = False
        self._thread           = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print(f"[USB] Monitor started. Current drives: {self._known_drives}")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            try:
                current_drives = set(get_usb_drives())

                # New drive inserted
                new_drives = current_drives - self._known_drives
                for drive in new_drives:
                    print(f"[USB] Drive inserted: {drive}")
                    if self.on_drive_inserted:
                        self.on_drive_inserted(drive)

                # Drive removed
                removed_drives = self._known_drives - current_drives
                for drive in removed_drives:
                    print(f"[USB] Drive removed: {drive}")
                    if self.on_drive_removed:
                        self.on_drive_removed(drive)

                self._known_drives = current_drives

            except Exception as e:
                print(f"[USB] Monitor error: {e}")

            time.sleep(2)  # Check every 2 seconds
