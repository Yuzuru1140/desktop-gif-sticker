import sys
import os
import ctypes
from PIL import Image, ImageDraw, ImageSequence
from PyQt6.QtCore import Qt, QPoint, QSize, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QCursor, QImage, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QFileDialog, QVBoxLayout, QInputDialog
)

# Windows Win32 API for enforcing topmost overlay above fullscreen apps & borderless windows
IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    user32 = ctypes.windll.user32
    user32.SetWindowPos.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_uint
    ]
    user32.SetWindowPos.restype = ctypes.c_bool

    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040


def get_resource_path(relative_path=""):
    """Returns absolute path to resource, compatible with PyInstaller --onefile and standard dev."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base_path, relative_path))

def get_available_gifs():
    """Scans for GIF files in bundled assets and local user directories."""
    found = {}
    
    # 1. Bundled assets directory
    bundled_dir = get_resource_path("assets")
    if os.path.exists(bundled_dir):
        for f in os.listdir(bundled_dir):
            if f.lower().endswith(".gif"):
                found[f] = os.path.join(bundled_dir, f)

    # 2. Local assets next to .exe or script
    exe_dir = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
    local_assets = os.path.join(exe_dir, "assets")
    if os.path.exists(local_assets) and os.path.abspath(local_assets) != os.path.abspath(bundled_dir):
        for f in os.listdir(local_assets):
            if f.lower().endswith(".gif"):
                found[f] = os.path.join(local_assets, f)

    # 3. Direct files next to .exe
    if os.path.exists(exe_dir):
        for f in os.listdir(exe_dir):
            if f.lower().endswith(".gif"):
                found[f] = os.path.join(exe_dir, f)

    return found


class GifLoaderWorker(QThread):
    finished_loading = pyqtSignal(list, list, QSize)
    error_loading = pyqtSignal(str)

    def __init__(self, file_path, bg_mode="auto", bg_tolerance=35, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.bg_mode = bg_mode
        self.bg_tolerance = bg_tolerance

    def run(self):
        try:
            if not os.path.exists(self.file_path):
                self.error_loading.emit("File tidak ditemukan.")
                return

            im = Image.open(self.file_path)
            qpixmaps = []
            delays = []

            # Extract base frame dimensions (capped at 240px for desktop performance)
            orig_w, orig_h = im.size
            max_dim = max(orig_w, orig_h)
            factor = min(2.5, max(1.0, 180.0 / max_dim))
            base_size = QSize(int(orig_w * factor), int(orig_h * factor))

            # Limit max processing dimension to 240px for huge GIFs (prevents RAM spikes)
            target_scale_size = None
            if orig_w > 240 or orig_h > 240:
                scale_ratio = 240.0 / max_dim
                target_scale_size = (int(orig_w * scale_ratio), int(orig_h * scale_ratio))

            frame_idx = 0
            for frame in ImageSequence.Iterator(im):
                frame_idx += 1
                if frame_idx > 300:  # Safety cap for infinite loops
                    break

                # Convert to RGBA for alpha channel transparency
                f = frame.convert("RGBA")

                # Downscale if larger than 240px
                if target_scale_size:
                    f = f.resize(target_scale_size, Image.Resampling.LANCZOS)

                w, h = f.size

                # Background transparency processing
                if self.bg_mode != "none":
                    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
                    corner_alphas = [f.getpixel(pt)[3] for pt in corners]
                    already_transparent = any(a == 0 for a in corner_alphas)

                    if not (self.bg_mode == "auto" and already_transparent):
                        tol = self.bg_tolerance
                        # Flood fill from each of the 4 corners
                        for pt in corners:
                            pix = f.getpixel(pt)
                            if pix[3] > 0:  # If pixel is opaque
                                should_fill = True
                                if self.bg_mode == "white":
                                    should_fill = (pix[0] >= 220 and pix[1] >= 220 and pix[2] >= 220)
                                elif self.bg_mode == "black":
                                    should_fill = (pix[0] <= 35 and pix[1] <= 35 and pix[2] <= 35)
                                elif self.bg_mode == "green":
                                    should_fill = (pix[1] > 180 and pix[0] < 100 and pix[2] < 100)

                                if should_fill:
                                    ImageDraw.floodfill(f, pt, (0, 0, 0, 0), thresh=tol)

                # Convert PIL RGBA image directly to QPixmap
                raw_bytes = f.tobytes("raw", "RGBA")
                qimg = QImage(raw_bytes, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
                qpixmaps.append(QPixmap.fromImage(qimg))

                # Extract frame duration
                d = frame.info.get("duration", im.info.get("duration", 80))
                delays.append(d if d and d > 10 else 80)

            if qpixmaps:
                self.finished_loading.emit(qpixmaps, delays, base_size)
            else:
                self.error_loading.emit("Tidak ada frame yang dapat dibaca.")

        except Exception as e:
            self.error_loading.emit(str(e))


class StickerWidget(QWidget):
    def __init__(self, gif_path=None, parent=None):
        super().__init__(parent)
        
        self.gif_path = gif_path
        self.drag_position = QPoint()
        self.is_locked = False
        self.is_always_on_top = True
        self.current_scale = 1.0
        self.base_size = QSize(160, 160)

        # Background transparency settings
        # Modes: "auto" (default), "white", "black", "green", "none"
        self.bg_mode = "auto"
        self.bg_tolerance = 35

        # FPS & Speed playback settings
        self.fps_mode = "default"        # "default" or "fixed"
        self.target_fps = 30             # target fps when in "fixed" mode
        self.speed_multiplier = 1.0      # speed multiplier (0.25x - 3.0x)

        # Animation state
        self.frames = []
        self.delays = []
        self.frame_idx = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.setSingleShot(True)
        self.anim_timer.timeout.connect(self.advance_frame)

        # Fullscreen overlay enforcement timer (keeps sticker topmost above fullscreen apps)
        self.topmost_timer = QTimer(self)
        self.topmost_timer.setInterval(1000)
        self.topmost_timer.timeout.connect(self.enforce_topmost)
        if self.is_always_on_top:
            self.topmost_timer.start()

        self.loader_thread = None

        self.init_ui()

    def init_ui(self):
        # Window attributes for transparent background & borderless floating window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        # Layout & Label for the GIF
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setScaledContents(True)
        self.layout.addWidget(self.label)

        if self.gif_path and os.path.exists(self.gif_path):
            self.load_gif(self.gif_path)
        else:
            self.label.setText("Drop GIF di sini\natau Klik Kanan")
            self.label.setStyleSheet("color: white; background: rgba(30,30,40,200); border-radius: 10px; padding: 12px;")
            self.resize(180, 80)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.enforce_topmost()

    def showEvent(self, event):
        super().showEvent(event)
        self.enforce_topmost()

    def enforce_topmost(self):
        """Ensures the floating sticker stays at the very top Z-order, even above fullscreen apps."""
        if not IS_WINDOWS or not self.is_always_on_top or not self.isVisible():
            return
        try:
            hwnd = int(self.winId())
            if hwnd:
                user32.SetWindowPos(
                    hwnd,
                    HWND_TOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                )
        except Exception:
            pass

    def load_gif(self, file_path):
        """Asynchronously loads and processes a GIF file in a background worker thread."""
        self.gif_path = os.path.abspath(file_path)
        self.anim_timer.stop()

        # Stop existing loader thread if running
        if self.loader_thread and self.loader_thread.isRunning():
            self.loader_thread.terminate()
            self.loader_thread.wait()

        # Start asynchronous worker
        self.loader_thread = GifLoaderWorker(
            self.gif_path,
            bg_mode=self.bg_mode,
            bg_tolerance=self.bg_tolerance,
            parent=self
        )
        self.loader_thread.finished_loading.connect(self.on_gif_loaded)
        self.loader_thread.error_loading.connect(self.on_gif_error)
        self.loader_thread.start()

    def on_gif_loaded(self, frames, delays, base_size):
        """Called when background worker finishes loading and processing frames."""
        self.frames = frames
        self.delays = delays
        self.base_size = base_size
        self.frame_idx = 0
        self.current_scale = 1.0

        self.apply_size()
        self.label.setStyleSheet("")

        if self.frames:
            self.label.setPixmap(self.frames[0])
            if len(self.frames) > 1:
                self.anim_timer.start(self.get_current_frame_delay())

    def on_gif_error(self, err_msg):
        self.label.setText(f"Gagal memuat:\n{err_msg}")
        self.label.setStyleSheet("color: #ff5555; background: rgba(30,30,40,220); border-radius: 8px; padding: 8px;")
        self.resize(180, 80)

    def get_native_fps(self):
        """Calculates approximate native FPS based on average frame delay."""
        if not self.delays:
            return 12
        avg_delay = sum(self.delays) / max(1, len(self.delays))
        if avg_delay <= 0:
            return 12
        return max(1, round(1000.0 / avg_delay))

    def get_current_frame_delay(self):
        """Calculates millisecond delay for current frame based on FPS mode and speed multiplier."""
        if not self.delays:
            return 80
        if self.fps_mode == "fixed" and self.target_fps > 0:
            base_delay = 1000.0 / self.target_fps
        else:
            base_delay = self.delays[self.frame_idx] if self.frame_idx < len(self.delays) else 80

        final_delay = max(5, int(base_delay / self.speed_multiplier))
        return final_delay

    def set_fps_mode(self, mode, target_fps=None):
        """Switches FPS mode ('default' or 'fixed') and updates playback speed live."""
        self.fps_mode = mode
        if target_fps is not None:
            self.target_fps = target_fps
            self.speed_multiplier = 1.0  # Reset speed multiplier when picking explicit fixed FPS
        if self.anim_timer.isActive() or len(self.frames) > 1:
            self.anim_timer.stop()
            self.anim_timer.start(self.get_current_frame_delay())

    def set_speed_multiplier(self, multiplier):
        """Sets playback speed multiplier (e.g. 0.5x, 2.0x) and applies immediately."""
        self.speed_multiplier = multiplier
        if self.anim_timer.isActive() or len(self.frames) > 1:
            self.anim_timer.stop()
            self.anim_timer.start(self.get_current_frame_delay())

    def prompt_custom_fps(self):
        """Displays dialog for custom target FPS input."""
        current = self.target_fps if self.fps_mode == "fixed" else self.get_native_fps()
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Atur Custom FPS")
        dialog.setLabelText("Masukkan target Frame Per Second (1 - 120 FPS):")
        dialog.setIntRange(1, 120)
        dialog.setIntValue(current)
        dialog.setIntStep(1)
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QLabel {
                color: #cdd6f4;
                font-size: 13px;
                padding: 4px;
            }
            QSpinBox {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 14px;
            }
            QPushButton {
                background-color: #313244;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px 14px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #45475a;
                color: #89b4fa;
            }
        """)
        if dialog.exec():
            fps = dialog.intValue()
            if fps > 0:
                self.set_fps_mode("fixed", fps)

    def advance_frame(self):
        """Displays next frame in the animation loop."""
        if not self.frames:
            return

        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        self.label.setPixmap(self.frames[self.frame_idx])

        # Schedule next frame with dynamically calculated delay
        self.anim_timer.start(self.get_current_frame_delay())

    def apply_size(self):
        w = max(40, int(self.base_size.width() * self.current_scale))
        h = max(40, int(self.base_size.height() * self.current_scale))
        target_size = QSize(w, h)
        self.label.resize(target_size)
        self.resize(target_size)

    # --- Mouse Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_locked:
                self.drag_position = event.globalPosition().toPoint() - self.pos()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.is_locked:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.PointingHandCursor if not self.is_locked else Qt.CursorShape.ArrowCursor)
            event.accept()

    # --- Mouse Wheel for Zoom / Scaling ---
    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            self.current_scale = min(5.0, self.current_scale * 1.1)
        elif angle < 0:
            self.current_scale = max(0.25, self.current_scale * 0.9)
        
        self.apply_size()
        event.accept()

    # --- Drag & Drop GIF file onto sticker ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = os.path.splitext(url.toLocalFile())[1].lower()
                if ext in ['.gif', '.png', '.webp', '.jpg', '.jpeg']:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if os.path.exists(file_path):
                self.load_gif(file_path)
                event.acceptProposedAction()
                return

    # --- Context Menu (Right-Click) ---
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #45475a;
                border-radius: 8px;
                padding: 6px;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 22px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #313244;
                color: #89b4fa;
            }
            QMenu::separator {
                height: 1px;
                background: #313244;
                margin: 4px 6px;
            }
        """)

        # 1. Preset Characters (Internal & External Discoveries)
        gifs_dict = get_available_gifs()
        if gifs_dict:
            preset_menu = menu.addMenu("👾 Karakter Bawaan")
            for gif_name, full_path in sorted(gifs_dict.items()):
                name_display = os.path.splitext(gif_name)[0].replace("_", " ").replace("-", " ").capitalize()
                act = preset_menu.addAction(f"🔹 {name_display}")
                act.triggered.connect(lambda ch, p=full_path: self.load_gif(p))

        # 2. Browse Custom GIF
        browse_act = menu.addAction("📁 Buka File GIF Lain...")
        browse_act.triggered.connect(self.browse_gif)

        # 3. Add New Sticker
        duplicate_act = menu.addAction("✨ Tambah Stiker Baru")
        duplicate_act.triggered.connect(self.add_new_sticker)

        menu.addSeparator()

        # 4. Background Removal (Transparansi) Menu
        bg_menu = menu.addMenu("🎨 Hapus Background (Transparan)")
        bg_group = QActionGroup(bg_menu)

        modes = [
            ("auto", "✨ Otomatis (Rekomendasi)"),
            ("white", "⚪ Hapus Background Putih"),
            ("black", "⚫ Hapus Background Hitam"),
            ("green", "🟢 Hapus Green Screen"),
            ("none", "🚫 Nonaktif (Warna Asli)")
        ]
        for mode_key, mode_title in modes:
            act = QAction(mode_title, bg_menu, checkable=True)
            if self.bg_mode == mode_key:
                act.setChecked(True)
            act.triggered.connect(lambda checked, m=mode_key: self.set_bg_mode(m))
            bg_group.addAction(act)
            bg_menu.addAction(act)

        bg_menu.addSeparator()
        tol_menu = bg_menu.addMenu("🎯 Toleransi Kehalusan")
        tol_group = QActionGroup(tol_menu)
        tolerances = [(15, "Rendah (15)"), (35, "Sedang (35 - Standar)"), (60, "Tinggi (60)")]
        for t_val, t_label in tolerances:
            t_act = QAction(t_label, tol_menu, checkable=True)
            if self.bg_tolerance == t_val:
                t_act.setChecked(True)
            t_act.triggered.connect(lambda checked, v=t_val: self.set_bg_tolerance(v))
            tol_group.addAction(t_act)
            tol_menu.addAction(t_act)

        # 5. FPS & Playback Speed Menu
        fps_menu = menu.addMenu("⚡ Kecepatan & FPS Animasi")
        fps_group = QActionGroup(fps_menu)

        native_fps = self.get_native_fps()
        default_act = QAction(f"🔄 Default (Asli GIF ~{native_fps} FPS)", fps_menu, checkable=True)
        default_act.setChecked(self.fps_mode == "default" and abs(self.speed_multiplier - 1.0) < 0.05)
        default_act.triggered.connect(lambda: self.set_fps_mode("default"))
        fps_group.addAction(default_act)
        fps_menu.addAction(default_act)

        fps_menu.addSeparator()

        fps_presets = [
            (10, "⚡ 10 FPS (Santai)"),
            (15, "⚡ 15 FPS"),
            (24, "⚡ 24 FPS (Cinematic)"),
            (30, "⚡ 30 FPS (Standar / Halus)"),
            (60, "⚡ 60 FPS (Sangat Cepat)")
        ]
        for fps_val, fps_label in fps_presets:
            act = QAction(fps_label, fps_menu, checkable=True)
            act.setChecked(self.fps_mode == "fixed" and self.target_fps == fps_val and abs(self.speed_multiplier - 1.0) < 0.05)
            act.triggered.connect(lambda checked, v=fps_val: self.set_fps_mode("fixed", v))
            fps_group.addAction(act)
            fps_menu.addAction(act)

        is_custom_fixed = (self.fps_mode == "fixed" and self.target_fps not in [10, 15, 24, 30, 60] and abs(self.speed_multiplier - 1.0) < 0.05)
        custom_label = f"✏️ Kustom FPS ({self.target_fps} FPS)..." if is_custom_fixed else "✏️ Kustom FPS..."
        custom_act = QAction(custom_label, fps_menu, checkable=True)
        custom_act.setChecked(is_custom_fixed)
        custom_act.triggered.connect(self.prompt_custom_fps)
        fps_group.addAction(custom_act)
        fps_menu.addAction(custom_act)

        fps_menu.addSeparator()

        # Speed Multiplier Submenu
        speed_menu = fps_menu.addMenu("⏩ Pengali Kecepatan (Speed)")
        speed_group = QActionGroup(speed_menu)
        speeds = [
            (0.25, "0.25x (Sangat Lambat)"),
            (0.5, "0.5x (Lambat)"),
            (0.75, "0.75x"),
            (1.0, "1.0x (Normal)"),
            (1.25, "1.25x"),
            (1.5, "1.5x"),
            (2.0, "2.0x (Cepat)"),
            (3.0, "3.0x (Sangat Cepat)")
        ]
        for sp_val, sp_label in speeds:
            sp_act = QAction(sp_label, speed_menu, checkable=True)
            sp_act.setChecked(abs(self.speed_multiplier - sp_val) < 0.05)
            sp_act.triggered.connect(lambda checked, s=sp_val: self.set_speed_multiplier(s))
            speed_group.addAction(sp_act)
            speed_menu.addAction(sp_act)

        # 6. Window Opacity Menu
        opacity_menu = menu.addMenu("🌓 Transparansi Layar")
        opacity_group = QActionGroup(opacity_menu)
        for pct in [100, 85, 70, 50, 30]:
            action = QAction(f"{pct}%", opacity_menu, checkable=True)
            current_pct = int(round(self.windowOpacity() * 100))
            if abs(current_pct - pct) < 8:
                action.setChecked(True)
            action.triggered.connect(lambda checked, p=pct: self.setWindowOpacity(p / 100.0))
            opacity_group.addAction(action)
            opacity_menu.addAction(action)

        # 6. Lock Position
        lock_label = "🔒 Kunci Posisi (Anti-geser)" if not self.is_locked else "🔓 Buka Kunci Posisi"
        lock_act = menu.addAction(lock_label)
        lock_act.triggered.connect(self.toggle_lock)

        # 7. Always on Top toggle
        top_act = menu.addAction("📌 Selalu di Depan (Overlay Layar & Fullscreen)")
        top_act.setCheckable(True)
        top_act.setChecked(self.is_always_on_top)
        top_act.triggered.connect(self.toggle_always_on_top)

        # 8. Reset Size
        reset_act = menu.addAction("🔄 Reset Ukuran")
        reset_act.triggered.connect(self.reset_size)

        menu.addSeparator()

        # 9. Close This Sticker
        close_act = menu.addAction("❌ Tutup Stiker Ini")
        close_act.triggered.connect(self.close)

        # 10. Quit All
        exit_act = menu.addAction("🚪 Tutup Semua & Keluar")
        exit_act.triggered.connect(QApplication.instance().quit)

        menu.exec(QCursor.pos())

    def set_bg_mode(self, mode):
        self.bg_mode = mode
        if self.gif_path:
            self.load_gif(self.gif_path)

    def set_bg_tolerance(self, tol):
        self.bg_tolerance = tol
        if self.gif_path:
            self.load_gif(self.gif_path)

    def browse_gif(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Pilih Animasi GIF",
            "",
            "Animasi GIF (*.gif);;Semua Gambar (*.gif *.png *.webp *.jpg)"
        )
        if file_name:
            self.load_gif(file_name)

    def add_new_sticker(self):
        new_widget = StickerWidget(gif_path=self.gif_path)
        new_widget.bg_mode = self.bg_mode
        new_widget.bg_tolerance = self.bg_tolerance
        new_widget.fps_mode = self.fps_mode
        new_widget.target_fps = self.target_fps
        new_widget.speed_multiplier = self.speed_multiplier
        new_widget.move(self.pos() + QPoint(50, 50))
        new_widget.show()
        if not hasattr(QApplication.instance(), "stickers"):
            QApplication.instance().stickers = []
        QApplication.instance().stickers.append(new_widget)

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.setCursor(Qt.CursorShape.ArrowCursor if self.is_locked else Qt.CursorShape.PointingHandCursor)

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        flags = self.windowFlags()
        if self.is_always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.show()
            self.enforce_topmost()
            if not self.topmost_timer.isActive():
                self.topmost_timer.start(1000)
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
            self.setWindowFlags(flags)
            self.show()
            if self.topmost_timer.isActive():
                self.topmost_timer.stop()
            if IS_WINDOWS:
                try:
                    hwnd = int(self.winId())
                    if hwnd:
                        user32.SetWindowPos(
                            hwnd,
                            HWND_NOTOPMOST,
                            0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW
                        )
                except Exception:
                    pass

    def reset_size(self):
        self.current_scale = 1.0
        self.apply_size()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # Set Window / Taskbar Icon
    icon_path = get_resource_path("app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Priority default GIF
    available = get_available_gifs()
    default_gif = None
    priority_keys = ["herta-kurukuru.gif", "tenor.gif", "pikachu_white_bg.gif", "pikachu.gif"]
    for k in priority_keys:
        if k in available:
            default_gif = available[k]
            break
    if not default_gif and available:
        default_gif = next(iter(available.values()))

    sticker = StickerWidget(gif_path=default_gif)
    app.stickers = [sticker]

    screen = app.primaryScreen().geometry()
    sticker.move(screen.width() - 260, screen.height() - 320)
    sticker.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
