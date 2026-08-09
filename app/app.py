import os
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'model')

# ── Local imports ─────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inference       import BrainTumorModel, CLASS_COLORS
from usb_monitor     import USBMonitor, get_usb_drives, get_images_from_drive
from gradcam         import generate_gradcam_heatmap
from gpio_controller import alert_no_tumor, alert_tumor_detected, reset_gpio, cleanup
from logger          import log_result, get_log_path

# ── Theme ─────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG_DARK    = "#0d1117"
BG_CARD    = "#161b22"
BG_SIDEBAR = "#0d1117"
ACCENT     = "#1f6feb"
TEXT_WHITE = "#e6edf3"
TEXT_GRAY  = "#8b949e"
BORDER     = "#30363d"
GREEN      = "#3fb950"
RED        = "#f85149"
ORANGE     = "#f0883e"

class BrainTumorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Brain Tumor Detection System")
        self.geometry("1280x760")
        self.minsize(1100, 680)
        self.configure(fg_color=BG_DARK)

        # State
        self.model          = None
        self.current_image  = None
        self.usb_monitor    = None
        self.current_drive  = None
        self.image_list     = []
        self.selected_image = None

        # Load model
        self._load_model()

        # Build UI
        self._build_ui()

        # Start USB monitor
        self._start_usb_monitor()

        # Scan for existing drives on startup
        self.after(500, self._scan_existing_drives)

        # Handle close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Model Loading ─────────────────────────────────────────────
    def _load_model(self):
        try:
            self.model = BrainTumorModel(MODEL_DIR)
        except Exception as e:
            self.model = None
            print(f"[App] Model load error: {e}")

    # ── UI Construction ───────────────────────────────────────────
    def _build_ui(self):
        # Header
        self._build_header()

        # Main content
        content = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
        content.pack(fill="both", expand=True, padx=0, pady=0)
        content.grid_columnconfigure(0, weight=0, minsize=280)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # Left sidebar
        self._build_sidebar(content)

        # Right panel
        self._build_main_panel(content)

        # Status bar
        self._build_statusbar()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=64,
                              border_width=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Left: Title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)

        dot = ctk.CTkLabel(title_frame, text="⬤", font=("Arial", 14), text_color=ACCENT)
        dot.pack(side="left", padx=(0, 8))

        title = ctk.CTkLabel(title_frame, text="Brain Tumor Detection System",
                             font=("Arial", 18, "bold"), text_color=TEXT_WHITE)
        title.pack(side="left")

        sub = ctk.CTkLabel(title_frame, text=" — Embedded AI Diagnostic Device",
                           font=("Arial", 12), text_color=TEXT_GRAY)
        sub.pack(side="left")

        # Right: Model status
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=20)

        status_color = GREEN if self.model else RED
        status_text  = "● Model Ready" if self.model else "● Model Not Found"
        ctk.CTkLabel(right, text=status_text, font=("Arial", 12),
                     text_color=status_color).pack(side="right")

    def _build_sidebar(self, parent):
        sidebar = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=0,
                               border_width=1, border_color=BORDER)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        # USB Status Section
        usb_header = ctk.CTkFrame(sidebar, fg_color="transparent")
        usb_header.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkLabel(usb_header, text="USB DRIVE", font=("Arial", 10, "bold"),
                     text_color=TEXT_GRAY).pack(side="left")

        self.usb_status_dot = ctk.CTkLabel(usb_header, text="⬤", font=("Arial", 10),
                                            text_color=RED)
        self.usb_status_dot.pack(side="right")

        self.usb_label = ctk.CTkLabel(sidebar, text="No drive detected",
                                       font=("Arial", 11), text_color=TEXT_GRAY,
                                       wraplength=240)
        self.usb_label.pack(fill="x", padx=12, pady=(0, 8))

        # Divider
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=8, pady=4)

        # Browse button (for PC - browse folder)
        self.browse_btn = ctk.CTkButton(
            sidebar, text="📁  Browse Folder", font=("Arial", 12),
            fg_color=ACCENT, hover_color="#388bfd", corner_radius=6,
            height=34, command=self._browse_folder
        )
        self.browse_btn.pack(fill="x", padx=12, pady=(8, 4))

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            sidebar, text="↺  Refresh USB", font=("Arial", 12),
            fg_color=BG_DARK, hover_color=BORDER, corner_radius=6,
            height=34, border_width=1, border_color=BORDER,
            text_color=TEXT_WHITE, command=self._scan_existing_drives
        )
        self.refresh_btn.pack(fill="x", padx=12, pady=(0, 8))

        # Divider
        ctk.CTkFrame(sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=8, pady=4)

        # Image list label
        ctk.CTkLabel(sidebar, text="MRI IMAGES", font=("Arial", 10, "bold"),
                     text_color=TEXT_GRAY).pack(fill="x", padx=12, pady=(8, 4))

        # Image listbox
        self.image_listbox = ctk.CTkScrollableFrame(
            sidebar, fg_color=BG_DARK, corner_radius=6,
            border_width=1, border_color=BORDER
        )
        self.image_listbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.no_images_label = ctk.CTkLabel(
            self.image_listbox,
            text="Insert USB drive\nor browse a folder\nto see images",
            font=("Arial", 11), text_color=TEXT_GRAY, justify="center"
        )
        self.no_images_label.pack(pady=20)

    def _build_main_panel(self, parent):
        main = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=0)

        # Left: Original Image
        img_card = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=8,
                                border_width=1, border_color=BORDER)
        img_card.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))

        ctk.CTkLabel(img_card, text="MRI SCAN", font=("Arial", 10, "bold"),
                     text_color=TEXT_GRAY).pack(anchor="w", padx=12, pady=(10, 0))

        self.original_image_label = ctk.CTkLabel(
            img_card, text="No image selected\n\nSelect an image from\nthe left panel",
            font=("Arial", 12), text_color=TEXT_GRAY, image=None
        )
        self.original_image_label.pack(fill="both", expand=True, padx=8, pady=8)

        # Right: Heatmap
        heat_card = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=8,
                                 border_width=1, border_color=BORDER)
        heat_card.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))

        ctk.CTkLabel(heat_card, text="GRAD-CAM HEATMAP", font=("Arial", 10, "bold"),
                     text_color=TEXT_GRAY).pack(anchor="w", padx=12, pady=(10, 0))

        self.heatmap_label = ctk.CTkLabel(
            heat_card, text="Heatmap will appear\nafter analysis",
            font=("Arial", 12), text_color=TEXT_GRAY, image=None
        )
        self.heatmap_label.pack(fill="both", expand=True, padx=8, pady=8)

        # Bottom: Result panel
        self._build_result_panel(main)

    def _build_result_panel(self, parent):
        result_frame = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8,
                                    border_width=1, border_color=BORDER, height=220)
        result_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        result_frame.pack_propagate(False)
        result_frame.grid_columnconfigure(0, weight=1)
        result_frame.grid_columnconfigure(1, weight=0)

        # Left: Result text
        left = ctk.CTkFrame(result_frame, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=16, pady=12)

        self.result_label = ctk.CTkLabel(
            left, text="AWAITING ANALYSIS",
            font=("Arial", 26, "bold"), text_color=TEXT_GRAY
        )
        self.result_label.pack(anchor="w")

        self.confidence_label = ctk.CTkLabel(
            left, text="Select an MRI image and run analysis",
            font=("Arial", 13), text_color=TEXT_GRAY
        )
        self.confidence_label.pack(anchor="w", pady=(2, 0))

        # Probability bars
        self.prob_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.prob_frame.pack(fill="x", pady=(8, 0))

        self.prob_bars = {}
        labels = ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary']
        colors = [RED, ORANGE, GREEN, '#A855F7']
        for i, (lbl, col) in enumerate(zip(labels, colors)):
            row = ctk.CTkFrame(self.prob_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=lbl, font=("Arial", 10),
                         text_color=TEXT_WHITE, width=100).pack(side="left")
            bar = ctk.CTkProgressBar(row, height=10, fg_color=BORDER,
                                     progress_color=col, corner_radius=4)
            bar.set(0)
            bar.pack(side="left", fill="x", expand=True, padx=(4, 8))
            pct = ctk.CTkLabel(row, text="0%", font=("Arial", 10),
                               text_color=TEXT_GRAY, width=36)
            pct.pack(side="left")
            self.prob_bars[lbl] = (bar, pct)

        # Right: Analyse button
        right = ctk.CTkFrame(result_frame, fg_color="transparent")
        right.pack(side="right", padx=16, pady=12)

        self.analyse_btn = ctk.CTkButton(
            right, text="▶  ANALYSE", font=("Arial", 15, "bold"),
            fg_color=ACCENT, hover_color="#388bfd", corner_radius=8,
            height=50, width=160, command=self._run_analysis
        )
        self.analyse_btn.pack(pady=(0, 6))

        ctk.CTkButton(
            right, text="📋  View Log", font=("Arial", 11),
            fg_color="transparent", hover_color=BORDER, corner_radius=6,
            height=30, border_width=1, border_color=BORDER,
            text_color=TEXT_GRAY, command=self._open_log
        ).pack()

    def _build_statusbar(self):
        status = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0,
                               height=28, border_width=0)
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            status, text="Ready — Insert USB drive or browse folder to begin",
            font=("Arial", 10), text_color=TEXT_GRAY
        )
        self.status_label.pack(side="left", padx=12)

        # Platform indicator
        from gpio_controller import IS_RPI
        platform_text = "🔧 Raspberry Pi Mode" if IS_RPI else "💻 PC Mode"
        ctk.CTkLabel(status, text=platform_text, font=("Arial", 10),
                     text_color=TEXT_GRAY).pack(side="right", padx=12)

    # ── USB Handling ──────────────────────────────────────────────
    def _start_usb_monitor(self):
        self.usb_monitor = USBMonitor(
            on_drive_inserted=self._on_drive_inserted,
            on_drive_removed=self._on_drive_removed
        )
        self.usb_monitor.start()

    def _scan_existing_drives(self):
        drives = get_usb_drives()
        if drives:
            self._on_drive_inserted(drives[0])
        else:
            self._set_status("No USB drive found — try Browse Folder")

    def _on_drive_inserted(self, drive):
        self.after(0, lambda: self._update_drive_ui(drive, connected=True))

    def _on_drive_removed(self, drive):
        self.after(0, lambda: self._update_drive_ui(drive, connected=False))

    def _update_drive_ui(self, drive, connected):
        if connected:
            self.current_drive = drive
            self.usb_status_dot.configure(text_color=GREEN)
            self.usb_label.configure(text=f"Connected: {drive}", text_color=GREEN)
            self._set_status(f"USB drive connected: {drive} — Scanning for images...")
            self._load_images_from_path(drive)
        else:
            self.current_drive = None
            self.usb_status_dot.configure(text_color=RED)
            self.usb_label.configure(text="Drive removed", text_color=RED)
            self._clear_image_list()
            self._set_status("USB drive removed")

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select folder with MRI images")
        if folder:
            self.usb_status_dot.configure(text_color=GREEN)
            self.usb_label.configure(text=f"Folder: {os.path.basename(folder)}", text_color=GREEN)
            self._load_images_from_path(folder)
            self._set_status(f"Browsing folder: {folder}")

    def _load_images_from_path(self, path):
        images = get_images_from_drive(path)
        self.image_list = images
        self._populate_image_list(images)
        if images:
            self._set_status(f"Found {len(images)} MRI image(s) — Click an image to select it")
        else:
            self._set_status("No MRI images found in this location")

    def _clear_image_list(self):
        for widget in self.image_listbox.winfo_children():
            widget.destroy()
        self.no_images_label = ctk.CTkLabel(
            self.image_listbox,
            text="Insert USB drive\nor browse a folder",
            font=("Arial", 11), text_color=TEXT_GRAY, justify="center"
        )
        self.no_images_label.pack(pady=20)

    def _populate_image_list(self, images):
        # Clear existing
        for widget in self.image_listbox.winfo_children():
            widget.destroy()

        if not images:
            ctk.CTkLabel(
                self.image_listbox, text="No images found",
                font=("Arial", 11), text_color=TEXT_GRAY
            ).pack(pady=20)
            return

        for img_path in images:
            name = os.path.basename(img_path)
            btn = ctk.CTkButton(
                self.image_listbox,
                text=f"🧠 {name}",
                font=("Arial", 11),
                fg_color="transparent",
                hover_color=BORDER,
                text_color=TEXT_WHITE,
                anchor="w",
                height=32,
                corner_radius=4,
                command=lambda p=img_path: self._select_image(p)
            )
            btn.pack(fill="x", pady=1)

    def _select_image(self, image_path):
        self.selected_image = image_path
        self._display_original(image_path)
        self.heatmap_label.configure(text="Click ANALYSE\nto generate heatmap")
        self.result_label.configure(text="READY TO ANALYSE", text_color=ACCENT)
        self.confidence_label.configure(text=f"Selected: {os.path.basename(image_path)}")
        self._reset_prob_bars()
        reset_gpio()
        self._set_status(f"Selected: {os.path.basename(image_path)} — Click ANALYSE")

    def _display_original(self, image_path):
        try:
            img = Image.open(image_path).convert('RGB')
            img = img.resize((320, 300), Image.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(320, 300))
            self.original_image_label.configure(image=photo, text="")
            self.original_image_label._image = photo
        except Exception as e:
            self.original_image_label.configure(text=f"Cannot display image\n{e}")

    def _display_heatmap(self, heatmap_array):
        try:
            img = Image.fromarray(heatmap_array.astype(np.uint8))
            img = img.resize((320, 300), Image.LANCZOS)
            photo = ctk.CTkImage(light_image=img, dark_image=img, size=(320, 300))
            self.heatmap_label.configure(image=photo, text="")
            self.heatmap_label._image = photo
        except Exception as e:
            self.heatmap_label.configure(text=f"Heatmap error\n{e}")

    # ── Analysis ──────────────────────────────────────────────────
    def _run_analysis(self):
        if not self.selected_image:
            messagebox.showwarning("No Image", "Please select an MRI image first.")
            return
        if not self.model:
            messagebox.showerror("Model Error", "Model not loaded. Check model folder.")
            return

        self.analyse_btn.configure(state="disabled", text="Analysing...")
        self.result_label.configure(text="ANALYSING...", text_color=ACCENT)
        self.confidence_label.configure(text="Please wait...")
        self._set_status("Running AI analysis...")

        thread = threading.Thread(target=self._analysis_thread, daemon=True)
        thread.start()

    def _analysis_thread(self):
        try:
            # Run inference
            label, confidence, probs, _ = self.model.predict(self.selected_image)

            # Generate heatmap
            heatmap = generate_gradcam_heatmap(self.selected_image, MODEL_DIR)

            # Log result
            log_result(self.selected_image, label, confidence, probs)

            # GPIO alert
            if self.model.is_tumor(label):
                alert_tumor_detected()
            else:
                alert_no_tumor()

            # Update UI on main thread
            self.after(0, lambda: self._update_results(label, confidence, probs, heatmap))

        except Exception as e:
            print(f"[Analysis] Error: {e}")
            self.after(0, lambda: self._analysis_error(str(e)))

    def _update_results(self, label, confidence, probs, heatmap):
        is_tumor = label != 'No Tumor'
        color    = RED if is_tumor else GREEN

        self.result_label.configure(
            text=f"{'⚠ ' if is_tumor else '✓ '}{label.upper()}",
            text_color=color
        )
        self.confidence_label.configure(
            text=f"Confidence: {confidence:.1f}%   |   {'TUMOR DETECTED — Refer to specialist' if is_tumor else 'NO TUMOR DETECTED — Result appears normal'}",
            text_color=color
        )

        # Update probability bars
        bar_keys = ['Glioma', 'Meningioma', 'No Tumor', 'Pituitary']
        for i, key in enumerate(bar_keys):
            if key in self.prob_bars:
                bar, pct = self.prob_bars[key]
                val = float(probs[i])
                bar.set(val)
                pct.configure(text=f"{val*100:.0f}%")

        # Display heatmap
        if heatmap is not None:
            self._display_heatmap(heatmap)

        self.analyse_btn.configure(state="normal", text="▶  ANALYSE")
        self._set_status(f"Analysis complete — {label} ({confidence:.1f}% confidence)")

    def _analysis_error(self, error_msg):
        self.result_label.configure(text="ANALYSIS FAILED", text_color=RED)
        self.confidence_label.configure(text=error_msg)
        self.analyse_btn.configure(state="normal", text="▶  ANALYSE")
        self._set_status(f"Error: {error_msg}")

    def _reset_prob_bars(self):
        for bar, pct in self.prob_bars.values():
            bar.set(0)
            pct.configure(text="0%")

    # ── Utilities ─────────────────────────────────────────────────
    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    def _open_log(self):
        import subprocess
        log = get_log_path()
        if os.path.exists(log):
            if sys.platform == 'win32':
                os.startfile(log)
            else:
                subprocess.Popen(['xdg-open', log])
        else:
            messagebox.showinfo("Log", "No results logged yet.")

    def _on_close(self):
        if self.usb_monitor:
            self.usb_monitor.stop()
        cleanup()
        self.destroy()

def launch():
    app = BrainTumorApp()
    app.mainloop()
