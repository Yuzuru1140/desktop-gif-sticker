import sys
import os
import json
import ctypes
import traceback
import faulthandler
from datetime import datetime
from PIL import Image, ImageDraw, ImageSequence
from PyQt6.QtCore import Qt, QPoint, QSize, QTimer, QThread, pyqtSignal

try:
    import numpy as np  # Optional: makes background removal ~50x faster
except ImportError:
    np = None
from PyQt6.QtGui import QAction, QActionGroup, QCursor, QImage, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QMenu, QFileDialog, QVBoxLayout, QInputDialog, QSizePolicy
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


# --- Saved state (positions & settings of every sticker) ---
STATE_VERSION = 1


def get_state_path():
    """Settings live in %APPDATA%\\DesktopSticker (the install folder may be read-only)."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "DesktopSticker", "stickers.json")


_error_log_file = None  # kept open: faulthandler writes to it on a native crash


def install_error_logging():
    """Logs errors to %APPDATA%\\DesktopSticker\\error.log.

    Under pyw/the .exe there is no console, so errors used to be invisible. Also, by
    default PyQt6 aborts the WHOLE app on any unhandled Python error in a slot (every
    sticker vanished at once); with our own excepthook the error is logged and the
    stickers keep running.
    """
    global _error_log_file
    log_path = os.path.join(os.path.dirname(get_state_path()), "error.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if os.path.exists(log_path) and os.path.getsize(log_path) > 512 * 1024:
            os.replace(log_path, log_path + ".old")  # keep the log small
        _error_log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(_error_log_file)  # native crashes (segfault/abort)
    except OSError:
        _error_log_file = None

    def excepthook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        if _error_log_file is not None:
            try:
                _error_log_file.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] {text}")
            except (OSError, ValueError):
                pass
        if sys.__stderr__ is not None:
            sys.__stderr__.write(text)

    sys.excepthook = excepthook


def log_event(message):
    """Writes an informational line to error.log (e.g. why the app quit)."""
    if _error_log_file is not None:
        try:
            _error_log_file.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] INFO {message}\n")
        except (OSError, ValueError):
            pass


def quit_app(reason):
    """The only intended way to quit: logs why, then quits."""
    app = QApplication.instance()
    if app is not None:
        app.quit_reason = reason
        app.quit()


def load_state():
    """Returns the list of saved sticker dicts, or [] if missing/corrupt."""
    try:
        # utf-8-sig: also accept a file saved with a BOM (e.g. edited by hand in an editor)
        with open(get_state_path(), "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
        stickers = data.get("stickers", []) if isinstance(data, dict) else []
        return [s for s in stickers if isinstance(s, dict)]
    except (OSError, ValueError):
        return []


def save_state(stickers):
    """Writes all stickers to disk atomically. An empty list is never written, so
    the last layout survives the app closing."""
    states = []
    for s in stickers:
        try:
            states.append(s.to_state())
        except RuntimeError:  # underlying Qt widget already deleted
            pass
    if not states:
        return
    path = get_state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"version": STATE_VERSION, "stickers": states}, fh, indent=2)
        os.replace(tmp, path)
    except OSError:
        pass


def request_save():
    """Schedules a save shortly after the last change (debounced)."""
    app = QApplication.instance()
    timer = getattr(app, "save_timer", None) if app else None
    if timer is not None and not getattr(app, "final_state_saved", False):
        timer.start()


def resolve_gif_path(path, name, available):
    """Finds a saved GIF again: same path, else same file name among the bundled/local GIFs
    (the bundled folder of the .exe is a new temp folder on every launch)."""
    if path and os.path.exists(path):
        return path
    if name and name in available:
        return available[name]
    return None


def _num(value, default, lo, hi, cast=float):
    """Reads a number from saved state, falling back to `default` if invalid."""
    try:
        v = cast(value)
    except (TypeError, ValueError):
        return default
    return min(hi, max(lo, v))


def _grow_along_rows(region, cand):
    """Expands `region` to cover every horizontal run of `cand` pixels it touches."""
    h, w = cand.shape
    flat = cand.ravel()
    starts = flat.copy()
    starts[1:] &= ~flat[:-1]
    starts[::w] = flat[::w]  # every row begins a new run
    run_id = np.cumsum(starts) * flat  # 0 = not a candidate pixel
    hit = np.zeros(int(run_id.max()) + 1, dtype=bool)
    hit[run_id[region.ravel() & flat]] = True
    hit[0] = False
    return hit[run_id].reshape(h, w)


def flood_clear(img, pt, tol):
    """Makes the 4-connected area around `pt` (colour distance <= tol) fully transparent.

    Same result as ImageDraw.floodfill(img, pt, (0, 0, 0, 0), thresh=tol), but vectorised
    with numpy when available (Pillow's floodfill is a slow pure-Python loop).
    """
    if np is None:
        ImageDraw.floodfill(img, pt, (0, 0, 0, 0), thresh=tol)
        return img

    x, y = pt
    arr = np.array(img, dtype=np.int16)
    seed = arr[y, x].copy()
    if int(np.abs(seed).sum()) <= tol:  # seed already looks like the fill colour
        return img
    cand = np.abs(arr - seed).sum(axis=2) <= tol
    region = np.zeros_like(cand)
    region[y, x] = True
    while True:
        grown = _grow_along_rows(region, cand)
        grown = _grow_along_rows(np.ascontiguousarray(grown.T), np.ascontiguousarray(cand.T)).T
        if np.array_equal(grown, region):
            break
        region = grown
    arr[region] = 0
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


class GifLoaderWorker(QThread):
    # Emits QImage (not QPixmap): QPixmap must only be created in the GUI thread.
    finished_loading = pyqtSignal(list, list, QSize)
    error_loading = pyqtSignal(str)

    def __init__(self, file_path, bg_mode="auto", bg_tolerance=35, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.bg_mode = bg_mode
        self.bg_tolerance = bg_tolerance
        self._cancelled = False

    def cancel(self):
        """Asks the worker to stop at the next frame (safe alternative to terminate())."""
        self._cancelled = True

    def run(self):
        try:
            if not os.path.exists(self.file_path):
                self.error_loading.emit("File tidak ditemukan.")
                return

            im = Image.open(self.file_path)
            qimages = []
            delays = []

            # Limit max processing dimension to 240px for huge GIFs (prevents RAM spikes)
            orig_w, orig_h = im.size
            max_dim = max(orig_w, orig_h)
            target_scale_size = None
            proc_w, proc_h = orig_w, orig_h
            if max_dim > 240:
                scale_ratio = 240.0 / max_dim
                proc_w = max(1, int(orig_w * scale_ratio))
                proc_h = max(1, int(orig_h * scale_ratio))
                target_scale_size = (proc_w, proc_h)

            # Default on-screen size is based on the processed frames, so big GIFs
            # are not stretched (blurry) beyond the 240px they were rendered at.
            # Small GIFs are still upscaled to ~180px so they remain visible.
            factor = min(2.5, max(1.0, 180.0 / max(proc_w, proc_h)))
            base_size = QSize(int(proc_w * factor), int(proc_h * factor))

            frame_idx = 0
            for frame in ImageSequence.Iterator(im):
                if self._cancelled:
                    return
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
                        auto_seeds = None
                        if self.bg_mode == "auto":
                            # A solid background touches several corners with the same colour.
                            # A corner unlike all the others is usually the character itself, and
                            # four different corners mean a scene/photo background: leave those alone.
                            colors = {pt: f.getpixel(pt) for pt in corners}
                            auto_seeds = {
                                pt for pt in corners
                                if any(q != pt and sum(abs(a - b) for a, b in zip(colors[pt], colors[q])) <= tol
                                       for q in corners)
                            }
                        # Flood fill from each of the 4 corners
                        for pt in corners:
                            if auto_seeds is not None and pt not in auto_seeds:
                                continue
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
                                    f = flood_clear(f, pt, tol)

                # Convert PIL RGBA image to QImage (converted to QPixmap in the GUI thread)
                raw_bytes = f.tobytes("raw", "RGBA")
                qimg = QImage(raw_bytes, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
                qimages.append(qimg)

                # Extract frame duration
                d = frame.info.get("duration", im.info.get("duration", 80))
                delays.append(d if d and d > 10 else 80)

            if self._cancelled:
                return
            if qimages:
                self.finished_loading.emit(qimages, delays, base_size)
            else:
                self.error_loading.emit("Tidak ada frame yang dapat dibaca.")

        except Exception as e:
            self.error_loading.emit(str(e))


class StickerWidget(QWidget):
    def __init__(self, gif_path=None, parent=None, bg_mode="auto", bg_tolerance=35,
                 fps_mode="default", target_fps=30, speed_multiplier=1.0,
                 scale=1.0, opacity=1.0, locked=False, always_on_top=True):
        super().__init__(parent)
        # Free the widget (and its timers/threads) when "Tutup Stiker Ini" is used
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self.gif_path = gif_path
        self.drag_position = QPoint()
        self.is_locked = locked
        self.is_always_on_top = always_on_top
        self.current_scale = scale
        self.base_size = QSize(160, 160)
        self._keep_scale_on_load = False

        # Background transparency settings
        # Modes: "auto" (default), "white", "black", "green", "none"
        self.bg_mode = bg_mode
        self.bg_tolerance = bg_tolerance

        # FPS & Speed playback settings
        self.fps_mode = fps_mode                  # "default" or "fixed"
        self.target_fps = target_fps              # target fps when in "fixed" mode
        self.speed_multiplier = speed_multiplier  # speed multiplier (0.25x - 3.0x)

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
        self.setWindowOpacity(opacity)

    @classmethod
    def from_state(cls, state, available, fallback_gif=None):
        """Recreates a sticker from a dict produced by to_state()."""
        gif = resolve_gif_path(state.get("gif_path"), state.get("gif_name"), available)
        bg_mode = state.get("bg_mode")
        fps_mode = state.get("fps_mode")
        sticker = cls(
            gif_path=gif or fallback_gif,
            bg_mode=bg_mode if bg_mode in ("auto", "white", "black", "green", "none") else "auto",
            bg_tolerance=_num(state.get("bg_tolerance"), 35, 0, 255, int),
            fps_mode=fps_mode if fps_mode in ("default", "fixed") else "default",
            target_fps=_num(state.get("target_fps"), 30, 1, 120, int),
            speed_multiplier=_num(state.get("speed_multiplier"), 1.0, 0.25, 3.0),
            scale=_num(state.get("scale"), 1.0, 0.25, 5.0) if gif else 1.0,
            opacity=_num(state.get("opacity"), 1.0, 0.1, 1.0),
            locked=bool(state.get("locked", False)),
            always_on_top=bool(state.get("always_on_top", True)),
        )
        x, y = state.get("x"), state.get("y")
        if isinstance(x, int) and isinstance(y, int):
            sticker.move(x, y)
        return sticker

    def to_state(self):
        """Everything needed to bring this sticker back after a restart."""
        return {
            "gif_path": self.gif_path,
            "gif_name": os.path.basename(self.gif_path) if self.gif_path else None,
            "x": self.x(),
            "y": self.y(),
            "scale": round(self.current_scale, 4),
            "bg_mode": self.bg_mode,
            "bg_tolerance": self.bg_tolerance,
            "fps_mode": self.fps_mode,
            "target_fps": self.target_fps,
            "speed_multiplier": self.speed_multiplier,
            "opacity": round(self.windowOpacity(), 2),
            "locked": self.is_locked,
            "always_on_top": self.is_always_on_top,
        }

    def init_ui(self):
        # Window attributes for transparent background & borderless floating window
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.is_always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        # Layout & Label for the GIF (named main_layout to avoid shadowing QWidget.layout())
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setScaledContents(True)
        # A QLabel holding a pixmap reports the pixmap's pixel size as its minimum size,
        # and the layout then refuses to make the window any smaller (scroll-to-shrink
        # stopped at the GIF's native size). Ignore it so apply_size() alone decides.
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.label.setMinimumSize(1, 1)
        self.main_layout.addWidget(self.label)

        if self.gif_path and os.path.exists(self.gif_path):
            # keep_scale: a restored sticker comes back at its saved zoom
            self.load_gif(self.gif_path, keep_scale=True)
        else:
            self.label.setText("Drop GIF di sini\natau Klik Kanan")
            self.label.setStyleSheet("color: white; background: rgba(30,30,40,200); border-radius: 10px; padding: 12px;")
            self.resize(180, 80)

        self.setCursor(Qt.CursorShape.ArrowCursor if self.is_locked else Qt.CursorShape.PointingHandCursor)
        self.enforce_topmost()

    def showEvent(self, event):
        super().showEvent(event)
        self.enforce_topmost()

    def close_by_user(self):
        """'Tutup Stiker Ini': removes just this sticker from the saved layout."""
        self._user_closing = True
        self.close()

    def closeEvent(self, event):
        """Stops timers and background loading so a closed sticker uses no CPU/RAM."""
        app = QApplication.instance()
        stickers = getattr(app, "stickers", None)
        if stickers is not None and self in stickers:
            if getattr(self, "_user_closing", False):
                if len(stickers) == 1:
                    # Closing the last sticker quits the app: remember it so it comes back
                    save_state(stickers)
                    app.final_state_saved = True
                stickers.remove(self)
                if stickers:
                    request_save()
                else:
                    # Last sticker closed: quit explicitly (Qt's automatic
                    # quit-on-last-window is disabled, see main()).
                    QTimer.singleShot(0, lambda: quit_app("stiker terakhir ditutup"))
            elif not getattr(app, "final_state_saved", False):
                # Qt 6 closes every window when the app quits ("Tutup Semua & Keluar",
                # Windows logoff). Save the whole layout once, while all stickers still exist.
                save_state(stickers)
                app.final_state_saved = True
        self.shutdown()
        super().closeEvent(event)

    def shutdown(self):
        """Stops animation/topmost timers and waits for all loader threads to finish."""
        self.anim_timer.stop()
        self.topmost_timer.stop()
        self.loader_thread = None
        for worker in self.findChildren(GifLoaderWorker):
            worker.cancel()
        for worker in self.findChildren(GifLoaderWorker):
            worker.wait()

    def enforce_topmost(self):
        """Ensures the floating sticker stays at the very top Z-order, even above fullscreen apps."""
        if not IS_WINDOWS or not self.is_always_on_top or not self.isVisible():
            return
        # Don't push the sticker above its own right-click menu or open dialogs
        if QApplication.activePopupWidget() or QApplication.activeModalWidget():
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

    def load_gif(self, file_path, keep_scale=False):
        """Asynchronously loads and processes a GIF file in a background worker thread.

        keep_scale=True keeps the current zoom (used when only background settings change).
        """
        self.gif_path = os.path.abspath(file_path)
        self._keep_scale_on_load = keep_scale

        # Cancel the previous loader cooperatively (terminate() can deadlock/crash Python).
        # Its results are ignored because it is no longer self.loader_thread.
        old = self.loader_thread
        if old is not None and old.isRunning():
            old.cancel()
            old.finished.connect(old.deleteLater)
        elif old is not None:
            old.deleteLater()

        # Start asynchronous worker
        worker = GifLoaderWorker(
            self.gif_path,
            bg_mode=self.bg_mode,
            bg_tolerance=self.bg_tolerance,
            parent=self
        )
        worker.finished_loading.connect(
            lambda frames, delays, size, w=worker: self.on_gif_loaded(w, frames, delays, size))
        worker.error_loading.connect(lambda msg, w=worker: self.on_gif_error(w, msg))
        self.loader_thread = worker
        worker.start()
        request_save()

    def on_gif_loaded(self, worker, images, delays, base_size):
        """Called when background worker finishes loading and processing frames."""
        if worker is not self.loader_thread:
            return  # stale result from a cancelled/replaced loader

        self.anim_timer.stop()
        self.frames = [QPixmap.fromImage(img) for img in images]
        self.delays = delays
        self.base_size = base_size
        self.frame_idx = 0
        if not self._keep_scale_on_load:
            self.current_scale = 1.0

        self.apply_size()
        self.keep_on_screen()
        self.label.setStyleSheet("")
        request_save()  # size/position may have changed

        if self.frames:
            self.label.setPixmap(self.frames[0])
            if len(self.frames) > 1:
                self.anim_timer.start(self.get_current_frame_delay())

    def on_gif_error(self, worker, err_msg):
        if worker is not self.loader_thread:
            return
        self.anim_timer.stop()
        self.frames = []
        self.delays = []
        self.label.clear()
        self.label.setText(f"Gagal memuat:\n{err_msg}")
        self.label.setStyleSheet("color: #ff5555; background: rgba(30,30,40,220); border-radius: 8px; padding: 8px;")
        self.resize(180, 80)

    def keep_on_screen(self):
        """Moves the sticker back inside the visible screen area if it sticks out."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = min(self.x(), geo.x() + geo.width() - self.width())
        y = min(self.y(), geo.y() + geo.height() - self.height())
        x = max(x, geo.x())
        y = max(y, geo.y())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

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
        # Picking "Default" or an explicit FPS resets the speed multiplier to 1.0x
        self.speed_multiplier = 1.0
        if self.anim_timer.isActive() or len(self.frames) > 1:
            self.anim_timer.stop()
            self.anim_timer.start(self.get_current_frame_delay())
        request_save()

    def set_speed_multiplier(self, multiplier):
        """Sets playback speed multiplier (e.g. 0.5x, 2.0x) and applies immediately."""
        self.speed_multiplier = multiplier
        if self.anim_timer.isActive() or len(self.frames) > 1:
            self.anim_timer.stop()
            self.anim_timer.start(self.get_current_frame_delay())
        request_save()

    def set_opacity(self, value):
        self.setWindowOpacity(value)
        request_save()

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
            request_save()  # remember the new position after a drag
            event.accept()

    # --- Mouse Wheel for Zoom / Scaling ---
    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            self.current_scale = min(5.0, self.current_scale * 1.1)
        elif angle < 0:
            self.current_scale = max(0.25, self.current_scale * 0.9)

        self.apply_size()
        request_save()
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
            action.triggered.connect(lambda checked, p=pct: self.set_opacity(p / 100.0))
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
        close_act.triggered.connect(self.close_by_user)

        # 10. Quit All
        exit_act = menu.addAction("🚪 Tutup Semua & Keluar")
        exit_act.triggered.connect(lambda: quit_app("menu Tutup Semua & Keluar"))

        menu.exec(QCursor.pos())

    def set_bg_mode(self, mode):
        self.bg_mode = mode
        if self.gif_path:
            self.load_gif(self.gif_path, keep_scale=True)

    def set_bg_tolerance(self, tol):
        self.bg_tolerance = tol
        if self.gif_path:
            self.load_gif(self.gif_path, keep_scale=True)

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
        # Settings go through the constructor so they apply before the GIF starts loading
        new_widget = StickerWidget(
            gif_path=self.gif_path,
            bg_mode=self.bg_mode,
            bg_tolerance=self.bg_tolerance,
            fps_mode=self.fps_mode,
            target_fps=self.target_fps,
            speed_multiplier=self.speed_multiplier,
        )
        new_widget.move(self.pos() + QPoint(50, 50))
        new_widget.show()
        if not hasattr(QApplication.instance(), "stickers"):
            QApplication.instance().stickers = []
        QApplication.instance().stickers.append(new_widget)
        request_save()

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.setCursor(Qt.CursorShape.ArrowCursor if self.is_locked else Qt.CursorShape.PointingHandCursor)
        request_save()

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        request_save()
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
        request_save()

def main():
    install_error_logging()
    app = QApplication(sys.argv)
    # Never let Qt quit on its own. Stickers are Qt.Tool windows, which Qt does not count
    # as "real" windows, so closing the "Buka File GIF" dialog looked like the last window
    # closing and Qt quit the whole app (exit code 0, every sticker gone). The app quits
    # only through quit_app(): "Tutup Semua & Keluar" or closing the last sticker.
    app.setQuitOnLastWindowClosed(False)
    app.quit_reason = None
    app.lastWindowClosed.connect(lambda: log_event("lastWindowClosed dari Qt diabaikan (aplikasi tetap jalan)"))

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

    # On quit, stop every sticker's loader thread first; destroying a running
    # QThread aborts the process ("QThread: Destroyed while thread is still running").
    # Also save the final layout ("Tutup Semua & Keluar") so it comes back next launch.
    def shutdown_all():
        log_event(f"aplikasi keluar: {app.quit_reason or 'TIDAK DIKETAHUI (bukan dari menu)'}")
        app.save_timer.stop()
        if not getattr(app, "final_state_saved", False):
            save_state(getattr(app, "stickers", []))
            app.final_state_saved = True
        for s in list(getattr(app, "stickers", [])):
            s.shutdown()
    app.aboutToQuit.connect(shutdown_all)

    # Debounced auto-save: changes are written ~0.5s after the last one
    app.save_timer = QTimer()
    app.save_timer.setSingleShot(True)
    app.save_timer.setInterval(500)
    app.save_timer.timeout.connect(lambda: save_state(app.stickers))

    # Restore the stickers from the last session, or start with the default one
    app.stickers = [StickerWidget.from_state(st, available, default_gif) for st in load_state()]
    if not app.stickers:
        sticker = StickerWidget(gif_path=default_gif)
        # Bottom-right of the usable screen area (respects taskbar & multi-monitor offsets);
        # keep_on_screen() pulls it back in once the real GIF size is known.
        geo = app.primaryScreen().availableGeometry()
        sticker.move(geo.x() + geo.width() - 260, geo.y() + geo.height() - 320)
        app.stickers = [sticker]

    for s in app.stickers:
        s.show()
        s.keep_on_screen()  # e.g. a monitor that was unplugged since last time

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
