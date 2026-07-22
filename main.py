"""
窗口锁定工具 - 主程序入口
识别并锁定窗口大小，最小化或关闭后重新打开仍保持锁定状态
使用 tkinter 做 UI，pystray 做系统托盘
"""

import sys
import os
import time
import threading
import logging
import ctypes
from ctypes import wintypes
from PIL import Image, ImageDraw, ImageTk
import pystray
import io
import tkinter as tk

from core.window_manager import WindowManager


def get_app_icon(process_path: str, size: int = 32):
    """从应用程序路径获取图标，返回 PIL Image 对象"""
    if not process_path or not os.path.exists(process_path):
        return None
    try:
        shell32 = ctypes.windll.shell32
        SHGFI_ICON = 0x000000100
        SHGFI_LARGEICON = 0x000000000
        SHGFI_SMALLICON = 0x000000001
        SHGFI_USEFILEATTRIBUTES = 0x000000010
        icon_flag = SHGFI_SMALLICON if size <= 16 else SHGFI_LARGEICON

        class SHFILEINFO(ctypes.Structure):
            _fields_ = [
                ("hIcon", wintypes.HICON),
                ("iIcon", ctypes.c_int),
                ("dwAttributes", ctypes.c_uint),
                ("szDisplayName", wintypes.WCHAR * 260),
                ("szTypeName", wintypes.WCHAR * 80),
            ]

        shfi = SHFILEINFO()
        result = shell32.SHGetFileInfoW(
            process_path, 0, ctypes.byref(shfi), ctypes.sizeof(shfi),
            SHGFI_ICON | icon_flag | SHGFI_USEFILEATTRIBUTES,
        )
        if result and shfi.hIcon:
            try:
                hdc_screen = ctypes.windll.user32.GetDC(0)
                hdc_mem = ctypes.windll.gdi32.CreateCompatibleDC(hdc_screen)
                hbmp = ctypes.windll.gdi32.CreateCompatibleBitmap(hdc_screen, size, size)
                old_bmp = ctypes.windll.gdi32.SelectObject(hdc_mem, hbmp)
                ctypes.windll.gdi32.SetBkColor(hdc_mem, 0x00FFFFFF)
                ctypes.windll.user32.FillRect(
                    hdc_mem, ctypes.byref(ctypes.wintypes.RECT(0, 0, size, size)),
                    ctypes.windll.gdi32.GetStockObject(0x00000005),
                )
                ctypes.windll.user32.DrawIconEx(hdc_mem, 0, 0, shfi.hIcon, size, size, 0, None, 0x0003)

                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                        ("biClrImportant", ctypes.c_uint32),
                    ]

                bmp_info = BITMAPINFOHEADER()
                bmp_info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmp_info.biWidth = size
                bmp_info.biHeight = -size
                bmp_info.biPlanes = 1
                bmp_info.biBitCount = 24
                bmp_info.biCompression = 0
                stride = (size * 3 + 3) // 4 * 4
                buf_size = stride * size
                buf = ctypes.create_string_buffer(buf_size)
                bits = ctypes.windll.gdi32.GetDIBits(hdc_mem, hbmp, 0, size, buf, ctypes.byref(bmp_info), 0)
                if bits > 0:
                    img = Image.frombuffer("RGB", (size, size), buf, "raw", "BGR", stride, 1)
                    ctypes.windll.gdi32.SelectObject(hdc_mem, old_bmp)
                    ctypes.windll.gdi32.DeleteObject(hbmp)
                    ctypes.windll.gdi32.DeleteDC(hdc_mem)
                    ctypes.windll.user32.ReleaseDC(0, hdc_screen)
                    ctypes.windll.user32.DestroyIcon(shfi.hIcon)
                    return img.resize((20, 20), Image.LANCZOS)
                ctypes.windll.gdi32.SelectObject(hdc_mem, old_bmp)
                ctypes.windll.gdi32.DeleteObject(hbmp)
                ctypes.windll.gdi32.DeleteDC(hdc_mem)
                ctypes.windll.user32.ReleaseDC(0, hdc_screen)
            except Exception as e:
                logger.debug(f"图标转换失败: {e}")
            ctypes.windll.user32.DestroyIcon(shfi.hIcon)
    except Exception as e:
        logger.debug(f"获取图标失败: {e}")
    return None


def setup_logging():
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
    except:
        base_dir = os.getcwd()
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'window_locker.log')
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='w'),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


logger = setup_logging()


# ─── 颜色方案 ─────────────────────────────────────────────
C_BG       = "#1e1e2e"
C_BG2      = "#252535"
C_BG3      = "#2a2a3a"
C_BORDER   = "#404050"
C_TEXT     = "#c0c0c0"
C_TEXT2    = "#808080"
C_ACCENT   = "#1565C0"
C_ACCENT2  = "#1976D2"
C_GREEN    = "#4CAF50"
C_GREEN_BG = "#1a2a1a"
C_GREEN_HD = "#1a3a1a"
C_ORANGE   = "#E65100"
C_RED      = "#e53935"


class WindowLockerApp:
    """窗口锁定应用主类"""

    def __init__(self):
        logger.debug("初始化 WindowLockerApp")
        self.wm = WindowManager()
        self._running = False
        self._icon = None
        self._root = None
        self._show_selector_event = threading.Event()
        self._menu_dirty = False
        self._menu_lock = threading.Lock()
        self._unlocked_items = []
        self._locked_items = []
        self._unlocked_cards = []
        self._locked_cards = []
        self._selected_info = None  # ("unlocked"|"locked", index)
        self._drag_start = None
        self._photo_refs = []       # 防止 PhotoImage 被回收

    # ─── 监控线程 ────────────────────────────────────────────
    def _monitor_loop(self):
        logger.debug("监控线程启动")
        while self._running:
            try:
                self.wm.enforce_locked_windows()
            except Exception as e:
                logger.error(f"监控循环错误: {e}", exc_info=True)
            time.sleep(0.5)
        logger.debug("监控线程退出")

    # ─── 托盘图标 ────────────────────────────────────────────
    def _mark_menu_dirty(self):
        with self._menu_lock:
            self._menu_dirty = True

    def _create_icon_image(self):
        size = 64
        image = Image.new('RGB', (size, size), color=(70, 130, 180))
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 28, 48, 52], fill=(255, 215, 0), outline=(184, 134, 11))
        draw.arc([22, 12, 42, 32], 0, 180, fill=(255, 215, 0), width=4)
        draw.ellipse([28, 34, 36, 42], fill=(70, 130, 180))
        draw.rectangle([30, 38, 34, 44], fill=(70, 130, 180))
        return image

    def _build_menu(self):
        try:
            items = [
                pystray.MenuItem("窗口锁定工具", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("打开主页面", self._on_show_windows, default=True),
                pystray.MenuItem("选择窗口锁定...", self._on_show_windows, default=False),
                pystray.Menu.SEPARATOR,
            ]
            try:
                locked = self.wm.get_locked_windows()
            except Exception:
                locked = []
            if locked:
                items.append(pystray.MenuItem("已锁定的窗口:", None, enabled=False))
                for w in locked:
                    title = w.title[:40] + "..." if len(w.title) > 40 else w.title
                    items.append(pystray.MenuItem(f"  {title}", self._create_unlock_callback(w.hwnd)))
                items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("退出", self._on_quit))
            return pystray.Menu(*items)
        except Exception as e:
            logger.error(f"构建菜单错误: {e}", exc_info=True)
            return pystray.Menu(
                pystray.MenuItem("窗口锁定工具", None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self._on_quit),
            )

    def _on_show_windows(self, icon=None, item=None):
        self._show_selector_event.set()

    def _create_unlock_callback(self, hwnd):
        def callback(icon, item):
            self._on_unlock_window(hwnd)
        return callback

    def _on_unlock_window(self, hwnd):
        try:
            self.wm.unlock_window(hwnd)
            self._mark_menu_dirty()
            if self._root:
                self._root.after(0, self._refresh_list)
        except Exception as e:
            logger.error(f"解锁窗口错误: {e}", exc_info=True)

    def _on_quit(self, icon=None, item=None):
        logger.info("菜单: 退出")
        try:
            self._running = False
            if self._icon:
                try:
                    self._icon.stop()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            logger.info("强制退出进程")
            try:
                current_pid = os.getpid()
                try:
                    import psutil
                    parent = psutil.Process(current_pid)
                    for child in parent.children(recursive=True):
                        try:
                            child.terminate()
                        except Exception:
                            pass
                    gone, alive = psutil.wait_procs(parent.children(recursive=True), timeout=3)
                    for p in alive:
                        try:
                            p.kill()
                        except Exception:
                            pass
                except ImportError:
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(current_pid)],
                                   capture_output=True, timeout=5)
            except Exception as e:
                logger.error(f"清理进程失败: {e}", exc_info=True)
            os._exit(0)

    def _menu_update_loop(self):
        while self._running:
            try:
                time.sleep(1)
                with self._menu_lock:
                    if self._menu_dirty and self._icon:
                        self._menu_dirty = False
                        try:
                            self._icon.menu = self._build_menu()
                        except Exception as e:
                            logger.error(f"更新菜单错误: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"菜单更新循环错误: {e}", exc_info=True)

    def _tray_loop(self):
        try:
            image = self._create_icon_image()
            menu = self._build_menu()
            self._icon = pystray.Icon("WindowLocker", image, "窗口锁定工具", menu)
            self._icon.run()
        except Exception as e:
            logger.error(f"托盘线程错误: {e}", exc_info=True)

    # ─── tkinter UI ──────────────────────────────────────────
    def run(self):
        logger.info("窗口锁定工具启动")
        self._running = True

        threading.Thread(target=self._monitor_loop, daemon=True, name="monitor").start()
        threading.Thread(target=self._menu_update_loop, daemon=True, name="menu-update").start()
        threading.Thread(target=self._tray_loop, daemon=True, name="tray").start()

        self._setup_ui()
        logger.info("程序已启动，右键点击托盘图标操作")
        self._root.mainloop()
        self._running = False

    def _setup_ui(self):
        root = tk.Tk()
        root.title("窗口锁定工具")
        root.geometry("640x520")
        root.resizable(False, False)
        root.configure(bg=C_BORDER)
        self._root = root

        # 居中显示
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = (sw - 640) // 2
        y = (sh - 520) // 2
        root.geometry(f"640x520+{x}+{y}")

        # 先显示默认标题栏，等布局完成后再隐藏
        root.update()
        root.after(10, lambda: root.overrideredirect(True))
        root.after(50, lambda: (root.lift(), root.focus_force(), root.attributes('-topmost', True)))
        root.after(500, lambda: root.attributes('-topmost', False))

        # 主容器（带1px边框效果）
        main_frame = tk.Frame(root, bg=C_BG, bd=0, highlightthickness=0)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._build_title_bar(main_frame)
        self._build_content(main_frame)
        self._build_buttons(main_frame)

        self._refresh_list()

        self._poll_show_request()

    # ─── 标题栏 ──────────────────────────────────────────────
    def _build_title_bar(self, parent):
        W = 638
        H = 52
        canvas = tk.Canvas(parent, height=H, highlightthickness=0, bg=C_ACCENT, cursor="arrow")
        canvas.pack(fill=tk.X)

        # 渐变背景: Blue700 -> Cyan600
        for y in range(H):
            t = y / (H - 1)
            r = int(21 * (1 - t) + 0 * t)
            g = int(101 * (1 - t) + 131 * t)
            b = int(192 * (1 - t) + 143 * t)
            canvas.create_line(0, y, W, y, fill=f"#{r:02x}{g:02x}{b:02x}")

        # 图标
        canvas.create_text(26, 26, text="\U0001F512", font=("Segoe UI Emoji", 15), fill="white")
        # 标题
        canvas.create_text(54, 17, text="窗口锁定工具",
                           font=("Microsoft YaHei", 12, "bold"), fill="white", anchor="w")
        canvas.create_text(54, 36, text="Window Locker",
                           font=("Consolas", 9), fill="#a0c0d0", anchor="w")

        # 最小化按钮
        btn_min = tk.Label(canvas, text="—", font=("Segoe UI", 11, "bold"),
                           fg="white", bg=C_ACCENT2, cursor="hand2", width=3)
        canvas.create_window(W - 76, 26, window=btn_min)
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#2a5db0"))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=C_ACCENT2))
        btn_min.bind("<Button-1>", lambda e: self._root.withdraw())

        # 关闭按钮
        btn_close = tk.Label(canvas, text="\u2715", font=("Segoe UI", 10, "bold"),
                             fg="white", bg=C_ACCENT2, cursor="hand2", width=3)
        canvas.create_window(W - 38, 26, window=btn_close)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=C_RED))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=C_ACCENT2))
        btn_close.bind("<Button-1>", lambda e: self._root.withdraw())

        # 拖拽移动
        canvas.bind("<Button-1>", self._on_title_press)
        canvas.bind("<B1-Motion>", self._on_title_drag)

        self._title_canvas = canvas

    def _on_title_press(self, event):
        self._drag_start = (event.x_root, event.y_root,
                            self._root.winfo_x(), self._root.winfo_y())

    def _on_title_drag(self, event):
        if self._drag_start:
            sx, sy, wx, wy = self._drag_start
            self._root.geometry(f"+{wx + event.x_root - sx}+{wy + event.y_root - sy}")

    # ─── 内容区（左右分栏+卡片列表） ─────────────────────────
    def _build_content(self, parent):
        content = tk.Frame(parent, bg=C_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        # ── 左列：未锁定 ──
        left = tk.Frame(content, bg=C_BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 3))

        # 表头
        lh = tk.Frame(left, bg=C_BG3, height=32)
        lh.pack(fill=tk.X)
        lh.pack_propagate(False)
        tk.Label(lh, text="\U0001F4CB  未锁定", font=("Microsoft YaHei", 9, "bold"),
                 fg=C_TEXT2, bg=C_BG3).pack(side=tk.LEFT, padx=10)
        self._unlocked_count_lbl = tk.Label(lh, text="0", font=("Microsoft YaHei", 8, "bold"),
                                            fg=C_TEXT2, bg="#3a3a4a", padx=7, pady=1)
        self._unlocked_count_lbl.pack(side=tk.RIGHT, padx=10)

        # 卡片滚动列表
        self._unlocked_canvas, self._unlocked_inner = self._create_card_list(left, C_BG2)
        self._unlocked_card_refs = []

        # ── 分隔线 ──
        tk.Frame(content, bg=C_BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=3)

        # ── 右列：已锁定 ──
        right = tk.Frame(content, bg=C_BG)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(3, 0))

        # 表头
        rh = tk.Frame(right, bg=C_GREEN_HD, height=32)
        rh.pack(fill=tk.X)
        rh.pack_propagate(False)
        tk.Label(rh, text="\U0001F512  已锁定", font=("Microsoft YaHei", 9, "bold"),
                 fg=C_GREEN, bg=C_GREEN_HD).pack(side=tk.LEFT, padx=10)
        self._locked_count_lbl = tk.Label(rh, text="0", font=("Microsoft YaHei", 8, "bold"),
                                          fg=C_GREEN, bg="#2a4a2a", padx=7, pady=1)
        self._locked_count_lbl.pack(side=tk.RIGHT, padx=10)

        # 卡片滚动列表
        self._locked_canvas, self._locked_inner = self._create_card_list(right, C_GREEN_BG)
        self._locked_card_refs = []

    def _create_card_list(self, parent, bg_color):
        """创建带滚动条的卡片列表容器，返回 (canvas, inner_frame)"""
        container = tk.Frame(parent, bg=bg_color, highlightthickness=1,
                             highlightbackground=C_BORDER)
        container.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        canvas = tk.Canvas(container, bg=bg_color, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview,
                                 bg=bg_color, troughcolor=bg_color,
                                 activebackground=C_BG3, width=6)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=bg_color, padx=6, pady=6)
        inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_config(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(e):
            canvas.itemconfig(inner_id, width=e.width)

        inner.bind("<Configure>", _on_inner_config)
        canvas.bind("<Configure>", _on_canvas_config)

        # 鼠标滚轮
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_wheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        return canvas, inner

    def _build_card(self, parent, window, idx, side_name, is_selected):
        """构建单个窗口卡片"""
        base_bg = C_BG2 if side_name == "unlocked" else C_GREEN_BG
        text_color = C_TEXT if side_name == "unlocked" else "#A5D6A7"
        sub_color = C_TEXT2 if side_name == "unlocked" else "#66BB6A"

        if is_selected:
            card_bg = C_ACCENT2
            border_color = "#00C8FF"
            title_color = "white"
            proc_color = "#E3F2FD"
        else:
            card_bg = base_bg
            border_color = C_BORDER if side_name == "unlocked" else "#2d5a2d"
            title_color = text_color
            proc_color = sub_color

        card = tk.Frame(parent, bg=border_color, bd=0)
        card.pack(fill=tk.X, pady=3)

        border_width = 2 if is_selected else 1
        inner = tk.Frame(card, bg=card_bg, padx=8, pady=7)
        inner.pack(fill=tk.X, padx=border_width, pady=border_width)

        # 图标
        icon_img = get_app_icon(window.process_path, size=32)
        if icon_img:
            photo = ImageTk.PhotoImage(icon_img.resize((22, 22), Image.LANCZOS))
            self._photo_refs.append(photo)
            icon_container = tk.Frame(inner, bg=card_bg, width=28, height=28)
            icon_container.pack(side=tk.LEFT, padx=(0, 8))
            icon_container.pack_propagate(False)
            icon_lbl = tk.Label(icon_container, image=photo, bg=card_bg)
            icon_lbl.pack(expand=True)
        else:
            icon_lbl = tk.Label(inner, text="\U0001FA9F", font=("Segoe UI Emoji", 13),
                                fg=proc_color, bg=card_bg)
            icon_lbl.pack(side=tk.LEFT, padx=(2, 10))

        # 文字区
        text_frame = tk.Frame(inner, bg=card_bg)
        text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        title = window.title[:22] + ("\u2026" if len(window.title) > 22 else "")
        tk.Label(text_frame, text=title, font=("Microsoft YaHei", 9, "bold"),
                 fg=title_color, bg=card_bg, anchor="w").pack(fill=tk.X)
        proc_name = window.process_name[:26] + ("\u2026" if len(window.process_name) > 26 else "")
        tk.Label(text_frame, text=proc_name, font=("Consolas", 8),
                 fg=proc_color, bg=card_bg, anchor="w").pack(fill=tk.X)

        # 置顶标记
        pin_label = None
        if window.pinned:
            pin_label = tk.Label(inner, text="\U0001F4CC", font=("Segoe UI Emoji", 10),
                                 bg=card_bg, fg=title_color)
            pin_label.pack(side=tk.RIGHT, padx=(4, 0))

        # 点击事件 + hover效果
        def _on_click(e):
            self._on_card_click(side_name, idx)

        def _on_enter(e):
            if not is_selected:
                inner.config(bg=C_BG3 if side_name == "unlocked" else "#233a23")
                for w in inner.winfo_children():
                    w.config(bg=C_BG3 if side_name == "unlocked" else "#233a23")
                for w in text_frame.winfo_children():
                    w.config(bg=C_BG3 if side_name == "unlocked" else "#233a23")

        def _on_leave(e):
            if not is_selected:
                inner.config(bg=card_bg)
                for w in inner.winfo_children():
                    w.config(bg=card_bg)
                for w in text_frame.winfo_children():
                    w.config(bg=card_bg)

        for w in [inner, card] + inner.winfo_children() + text_frame.winfo_children():
            w.bind("<Button-1>", _on_click)
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)

        return {
            'card': card,
            'inner': inner,
            'text_frame': text_frame,
            'pin_label': pin_label,
            'border_color': border_color,
            'card_bg': card_bg,
            'border_width': border_width,
            'side_name': side_name,
            'all_widgets': [inner, card] + inner.winfo_children() + text_frame.winfo_children()
        }

    # ─── 底部按钮栏 ──────────────────────────────────────────
    def _build_buttons(self, parent):
        bar = tk.Frame(parent, bg=C_BG)
        bar.pack(fill=tk.X, padx=8, pady=10)

        style = dict(font=("Microsoft YaHei", 9, "bold"), relief="flat",
                     cursor="hand2", bd=0, padx=14, pady=6)

        tk.Button(bar, text="\U0001F512 锁定/解锁", bg=C_ACCENT, fg="white",
                  activebackground=C_ACCENT2, activeforeground="white",
                  command=self._toggle_lock, **style).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="\U0001F4CC 置顶/取消", bg=C_ORANGE, fg="white",
                  activebackground="#EF6C00", activeforeground="white",
                  command=self._toggle_pin, **style).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="\U0001F504 刷新", bg=C_BG3, fg=C_TEXT,
                  activebackground="#444455", activeforeground="white",
                  command=self._refresh_list, **style).pack(side=tk.LEFT, padx=3)
        tk.Button(bar, text="\u2715 隐藏", bg=C_BG3, fg=C_TEXT,
                  activebackground="#444455", activeforeground="white",
                  command=self._root.withdraw, **style).pack(side=tk.LEFT, padx=3)

    # ─── 卡片点击/选择 ───────────────────────────────────────
    def _on_card_click(self, side_name, idx):
        self._selected_info = (side_name, idx)
        self._update_selection_visual()

    # ─── 操作按钮 ────────────────────────────────────────────
    def _toggle_lock(self):
        if not self._selected_info:
            return
        side, idx = self._selected_info
        items = self._unlocked_items if side == "unlocked" else self._locked_items
        if idx < len(items):
            w = items[idx]
            if w.locked:
                self.wm.unlock_window(w.hwnd)
                logger.info(f"解锁窗口: {w.title}")
            else:
                self.wm.lock_window(w.hwnd)
                logger.info(f"锁定窗口: {w.title}")
            self._refresh_list()
            self._mark_menu_dirty()

    def _toggle_pin(self):
        if not self._selected_info:
            return
        side, idx = self._selected_info
        items = self._unlocked_items if side == "unlocked" else self._locked_items
        cards = self._unlocked_cards if side == "unlocked" else self._locked_cards
        if idx < len(items):
            w = items[idx]
            if w.pinned:
                self.wm.unpin_window(w.hwnd)
                logger.info(f"取消置顶: {w.title}")
            else:
                self.wm.pin_window(w.hwnd)
                logger.info(f"置顶窗口: {w.title}")
            w.pinned = not w.pinned
            self._update_pin_icon(cards[idx], w.pinned)

    # ─── 刷新列表 ────────────────────────────────────────────
    def _refresh_list(self):
        if not self._root:
            return

        for child in self._unlocked_inner.winfo_children():
            child.destroy()
        for child in self._locked_inner.winfo_children():
            child.destroy()
        self._unlocked_items = []
        self._locked_items = []
        self._unlocked_cards = []
        self._locked_cards = []
        self._photo_refs.clear()

        try:
            windows = self.wm.get_all_windows()
        except Exception as e:
            logger.error(f"获取窗口列表失败: {e}")
            return

        unlocked_idx = 0
        locked_idx = 0
        for w in windows:
            if w.locked:
                is_sel = (self._selected_info is not None
                          and self._selected_info[0] == "locked"
                          and self._selected_info[1] == locked_idx)
                card_info = self._build_card(self._locked_inner, w, locked_idx, "locked", is_sel)
                self._locked_cards.append(card_info)
                self._locked_items.append(w)
                locked_idx += 1
            else:
                is_sel = (self._selected_info is not None
                          and self._selected_info[0] == "unlocked"
                          and self._selected_info[1] == unlocked_idx)
                card_info = self._build_card(self._unlocked_inner, w, unlocked_idx, "unlocked", is_sel)
                self._unlocked_cards.append(card_info)
                self._unlocked_items.append(w)
                unlocked_idx += 1

        self._unlocked_count_lbl.config(text=str(len(self._unlocked_items)))
        self._locked_count_lbl.config(text=str(len(self._locked_items)))

    def _update_selection_visual(self):
        """更新选中状态的视觉效果，不重建卡片"""
        cards = self._unlocked_cards if self._selected_info and self._selected_info[0] == "unlocked" else []
        cards += self._locked_cards if self._selected_info and self._selected_info[0] == "locked" else []

        for i, card_info in enumerate(self._unlocked_cards):
            is_sel = (self._selected_info == ("unlocked", i))
            self._apply_card_style(card_info, is_sel)

        for i, card_info in enumerate(self._locked_cards):
            is_sel = (self._selected_info == ("locked", i))
            self._apply_card_style(card_info, is_sel)

    def _apply_card_style(self, card_info, is_selected):
        """应用选中/未选中样式到卡片"""
        side_name = card_info['side_name']

        if is_selected:
            card_bg = C_ACCENT2
            border_color = "#00C8FF"
            title_color = "white"
            proc_color = "#E3F2FD"
            border_width = 2
        else:
            card_bg = C_BG2 if side_name == "unlocked" else C_GREEN_BG
            border_color = C_BORDER if side_name == "unlocked" else "#2d5a2d"
            title_color = C_TEXT if side_name == "unlocked" else "#A5D6A7"
            proc_color = C_TEXT2 if side_name == "unlocked" else "#66BB6A"
            border_width = 1

        card_info['card'].config(bg=border_color)
        card_info['inner'].config(bg=card_bg)
        card_info['text_frame'].config(bg=card_bg)
        
        # 更新边框宽度
        card_info['inner'].pack_configure(padx=border_width, pady=border_width)

        for w in card_info['inner'].winfo_children():
            w.config(bg=card_bg)
            if isinstance(w, tk.Label):
                if w['font'] == ("Microsoft YaHei", 9, "bold"):
                    w.config(fg=title_color)
                elif w['font'] == ("Consolas", 8):
                    w.config(fg=proc_color)
                elif w['font'] == ("Segoe UI Emoji", 10):
                    w.config(fg=title_color)

        for w in card_info['text_frame'].winfo_children():
            w.config(bg=card_bg)
            if isinstance(w, tk.Label):
                if w['font'] == ("Microsoft YaHei", 9, "bold"):
                    w.config(fg=title_color)
                elif w['font'] == ("Consolas", 8):
                    w.config(fg=proc_color)

    def _update_pin_icon(self, card_info, show_pin):
        """更新卡片的置顶图标显示"""
        if show_pin:
            if card_info['pin_label'] is None:
                side_name = card_info['side_name']
                card_bg = card_info['inner']['bg']
                is_selected = (card_bg == C_ACCENT2)
                title_color = "white" if is_selected else (
                    C_TEXT if side_name == "unlocked" else "#A5D6A7")
                pin_label = tk.Label(card_info['inner'], text="\U0001F4CC",
                                     font=("Segoe UI Emoji", 10),
                                     bg=card_bg, fg=title_color)
                pin_label.pack(side=tk.RIGHT, padx=(4, 0))
                card_info['pin_label'] = pin_label
        else:
            if card_info['pin_label'] is not None:
                card_info['pin_label'].destroy()
                card_info['pin_label'] = None

    # ─── 窗口显示/隐藏 ──────────────────────────────────────
    def _show_window(self):
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()
        self._refresh_list()

    def _poll_show_request(self):
        if not self._running:
            return
        try:
            if self._show_selector_event.is_set():
                self._show_selector_event.clear()
                self._show_window()
        except Exception as e:
            logger.error(f"检查显示请求错误: {e}")
        self._root.after(200, self._poll_show_request)


def main():
    try:
        app = WindowLockerApp()
        app.run()
    except Exception as e:
        logger.critical(f"程序异常退出: {e}", exc_info=True)
        try:
            ctypes.windll.user32.MessageBoxW(0, f"程序异常: {str(e)}", "错误", 0x10)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
