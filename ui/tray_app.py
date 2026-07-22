"""
系统托盘和右键菜单模块
提供系统托盘图标、右键菜单、窗口列表等功能
"""

import threading
import time
from typing import Optional, Callable

from PIL import Image, ImageDraw
import pystray


class TrayApp:
    """系统托盘应用类"""
    
    def __init__(self, window_manager, on_lock_window_callback: Callable = None, 
                 on_unlock_window_callback: Callable = None,
                 on_show_windows_callback: Callable = None,
                 on_quit_callback: Callable = None):
        """
        初始化托盘应用
        
        Args:
            window_manager: WindowManager实例
            on_lock_window_callback: 锁定窗口回调 (hwnd)
            on_unlock_window_callback: 解锁窗口回调 (hwnd)
            on_show_windows_callback: 显示窗口列表回调
            on_quit_callback: 退出程序回调
        """
        self.wm = window_manager
        self.on_lock_window = on_lock_window_callback
        self.on_unlock_window = on_unlock_window_callback
        self.on_show_windows = on_show_windows_callback
        self.on_quit = on_quit_callback
        
        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def _create_icon_image(self) -> Image.Image:
        """创建托盘图标"""
        size = 64
        image = Image.new('RGB', (size, size), color=(70, 130, 180))
        draw = ImageDraw.Draw(image)
        
        # 绘制锁图标
        # 锁身
        draw.rectangle([16, 28, 48, 52], fill=(255, 215, 0), outline=(184, 134, 11))
        # 锁扣
        draw.arc([22, 12, 42, 32], 0, 180, fill=(255, 215, 0), width=4)
        # 钥匙孔
        draw.ellipse([28, 34, 36, 42], fill=(70, 130, 180))
        draw.rectangle([30, 38, 34, 44], fill=(70, 130, 180))
        
        return image
    
    def _build_menu(self):
        """构建右键菜单"""
        if pystray is None:
            return None
        
        def make_lock_action(hwnd, title):
            def action(icon=None, item=None):
                if self.on_lock_window:
                    self.on_lock_window(hwnd)
            return action
        
        def make_unlock_action(hwnd, title):
            def action(icon=None, item=None):
                if self.on_unlock_window:
                    self.on_unlock_window(hwnd)
            return action
        
        menu_items = []
        
        menu_items.append(pystray.MenuItem("窗口锁定工具", None, enabled=False))
        menu_items.append(pystray.Menu.SEPARATOR)
        
        menu_items.append(pystray.MenuItem(
            "选择窗口锁定...",
            lambda icon, item: self.on_show_windows() if self.on_show_windows else None,
            default=False
        ))
        
        menu_items.append(pystray.Menu.SEPARATOR)
        
        locked_windows = self.wm.get_locked_windows()
        if locked_windows:
            menu_items.append(pystray.MenuItem("已锁定的窗口:", None, enabled=False))
            for window in locked_windows:
                title = window.title[:40] + "..." if len(window.title) > 40 else window.title
                menu_items.append(pystray.MenuItem(
                    f"  {title}",
                    make_unlock_action(window.hwnd, window.title),
                    default=False
                ))
            menu_items.append(pystray.Menu.SEPARATOR)
        
        menu_items.append(pystray.MenuItem(
            "退出",
            lambda icon, item: self._quit() if self.on_quit else None,
            default=False
        ))
        
        return pystray.Menu(*menu_items)
    
    def _update_menu(self):
        """更新菜单"""
        if self._icon and self._running:
            self._icon.menu = self._build_menu()
    
    def _quit(self):
        """退出程序"""
        self._running = False
        if self._icon:
            self._icon.stop()
        if self.on_quit:
            self.on_quit()
    
    def run(self):
        """运行托盘应用"""
        self._running = True
        
        image = self._create_icon_image()
        menu = self._build_menu()
        
        self._icon = pystray.Icon(
            "WindowLocker",
            image,
            "窗口锁定工具",
            menu
        )
        
        def run_icon():
            self._icon.run()
        
        self._thread = threading.Thread(target=run_icon, daemon=True)
        self._thread.start()
    
    def update(self):
        """更新菜单状态"""
        self._update_menu()
    
    def stop(self):
        """停止托盘应用"""
        self._running = False
        if self._icon:
            self._icon.stop()


class WindowSelector:
    """窗口选择对话框"""
    
    def __init__(self, window_manager, on_select_callback: Callable = None):
        """
        初始化窗口选择器
        
        Args:
            window_manager: WindowManager实例
            on_select_callback: 选择窗口回调 (hwnd, action) action: 'lock' 或 'unlock'
        """
        self.wm = window_manager
        self.on_select = on_select_callback
        self._window = None
    
    def show(self):
        """显示窗口选择列表"""
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            print("需要 tkinter 库 (Python内置)")
            return
        
        windows = self.wm.get_all_windows()
        
        root = tk.Tk()
        root.title("选择窗口")
        root.geometry("500x400")
        root.resizable(False, False)
        
        # 设置窗口图标和样式
        root.configure(bg='#f0f0f0')
        
        # 标题
        title_label = tk.Label(
            root, 
            text="选择要锁定的窗口:", 
            font=("Microsoft YaHei", 12),
            bg='#f0f0f0'
        )
        title_label.pack(pady=10)
        
        # 列表框
        frame = tk.Frame(root, bg='#f0f0f0')
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(
            frame, 
            font=("Microsoft YaHei", 10),
            yscrollcommand=scrollbar.set,
            height=15
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        # 存储窗口信息
        window_items = []
        
        for window in windows:
            locked_mark = "[已锁定]" if window.locked else ""
            title = window.title[:45] + "..." if len(window.title) > 45 else window.title
            item_text = f"{locked_mark} {window.process_name}: {title}"
            listbox.insert(tk.END, item_text)
            window_items.append(window)
        
        def on_lock_toggle():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                window = window_items[idx]
                if self.on_select:
                    action = 'unlock' if window.locked else 'lock'
                    self.on_select(window.hwnd, action)
                root.destroy()
        
        def on_refresh():
            listbox.delete(0, tk.END)
            window_items.clear()
            windows = self.wm.get_all_windows()
            for window in windows:
                locked_mark = "[已锁定]" if window.locked else ""
                title = window.title[:45] + "..." if len(window.title) > 45 else window.title
                item_text = f"{locked_mark} {window.process_name}: {title}"
                listbox.insert(tk.END, item_text)
                window_items.append(window)
        
        # 按钮
        btn_frame = tk.Frame(root, bg='#f0f0f0')
        btn_frame.pack(pady=10)
        
        lock_btn = tk.Button(
            btn_frame, 
            text="锁定/解锁",
            font=("Microsoft YaHei", 10),
            command=on_lock_toggle,
            width=12
        )
        lock_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = tk.Button(
            btn_frame, 
            text="刷新",
            font=("Microsoft YaHei", 10),
            command=on_refresh,
            width=8
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = tk.Button(
            btn_frame, 
            text="关闭",
            font=("Microsoft YaHei", 10),
            command=root.destroy,
            width=8
        )
        close_btn.pack(side=tk.LEFT, padx=5)
        
        # 双击锁定
        def on_double_click(event):
            on_lock_toggle()
        
        listbox.bind('<Double-Button-1>', on_double_click)
        
        # 居中显示
        root.update_idletasks()
        x = (root.winfo_screenwidth() - 500) // 2
        y = (root.winfo_screenheight() - 400) // 2
        root.geometry(f"500x400+{x}+{y}")
        
        root.mainloop()
