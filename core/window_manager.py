"""
窗口管理核心模块
负责枚举窗口、获取/设置窗口位置和大小、监控窗口状态
"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional, Dict
import time
import logging

logger = logging.getLogger("window_manager")


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.DWORD),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
    ]


@dataclass
class WindowInfo:
    """窗口信息数据结构"""
    hwnd: int
    title: str
    process_name: str
    rect: tuple  # (left, top, right, bottom)
    process_path: str = ""
    locked: bool = False
    locked_size: Optional[tuple] = None  # (width, height)
    locked_pos: Optional[tuple] = None   # (left, top)
    pinned: bool = False  # 是否置顶


class WindowManager:
    """窗口管理器核心类"""
    
    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        
        # 存储锁定的窗口信息: {hwnd: WindowInfo}
        self._locked_windows: Dict[int, WindowInfo] = {}
        
        # 存储置顶的窗口集合: {hwnd}
        self._pinned_windows: set = set()
        
        # 存储置顶窗口的进程名+标题，用于hwnd变化后保持置顶状态
        self._pinned_keys: set = set()
        
        # 设置函数原型
        self._setup_apis()
    
    def _setup_apis(self):
        """设置Windows API函数原型"""
        # EnumWindows
        self.EnumWindowsProcType = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self.user32.EnumWindows.argtypes = [self.EnumWindowsProcType, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        
        # GetWindowText
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        
        # GetWindowRect
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        
        # SetWindowPos
        self.user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user32.SetWindowPos.restype = wintypes.BOOL
        
        # GetWindowThreadProcessId
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        
        # IsWindowVisible
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        
        # GetModuleHandleW
        self.kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self.kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        
        # GetModuleFileNameW
        self.kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        self.kernel32.GetModuleFileNameW.restype = wintypes.DWORD
        
        # SetWindowPlacement
        self.user32.SetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
        self.user32.SetWindowPlacement.restype = wintypes.BOOL
        
        # GetWindowPlacement
        self.user32.GetWindowPlacement.argtypes = [wintypes.HWND, ctypes.POINTER(WINDOWPLACEMENT)]
        self.user32.GetWindowPlacement.restype = wintypes.BOOL
        
        # MoveWindow
        self.user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
        self.user32.MoveWindow.restype = wintypes.BOOL
        
        # GetWindowLongW
        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        self.user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowLongW.restype = wintypes.LONG
        
        # GetLastError
        self.kernel32.GetLastError.argtypes = []
        self.kernel32.GetLastError.restype = wintypes.DWORD
        
        # IsZoomed (最大化)
        self.user32.IsZoomed.argtypes = [wintypes.HWND]
        self.user32.IsZoomed.restype = wintypes.BOOL
        
        # SetWindowLongW
        self.user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        self.user32.SetWindowLongW.restype = wintypes.LONG
        
        # SetWindowPos with HWND_TOPMOST (用于置顶)
        self.HWND_TOPMOST = wintypes.HWND(-1)
        self.HWND_NOTOPMOST = wintypes.HWND(-2)
    
    def _get_window_title(self, hwnd: int) -> str:
        """获取窗口标题"""
        length = self.user32.GetWindowTextLengthW(hwnd) + 1
        if length <= 1:
            return ""
        buffer = ctypes.create_unicode_buffer(length)
        self.user32.GetWindowTextW(hwnd, buffer, length)
        return buffer.value
    
    def _get_process_name(self, hwnd: int) -> str:
        """获取进程名"""
        return self._get_process_path(hwnd).split('\\')[-1] if self._get_process_path(hwnd) else "unknown"
    
    def _get_process_path(self, hwnd: int) -> str:
        """获取进程完整路径"""
        try:
            import psutil
            process_id = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value:
                try:
                    proc = psutil.Process(process_id.value)
                    return proc.exe()
                except:
                    pass
        except ImportError:
            pass
        
        try:
            process_id = wintypes.DWORD()
            self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            if process_id.value:
                try:
                    handle = self.kernel32.OpenProcess(0x0400 | 0x0010, False, process_id.value)
                    if handle:
                        length = 260
                        buffer = ctypes.create_unicode_buffer(length)
                        if self.kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(ctypes.c_uint32(length))):
                            self.kernel32.CloseHandle(handle)
                            return buffer.value
                        self.kernel32.CloseHandle(handle)
                except:
                    pass
        except:
            pass
        return ""
    
    def _get_window_rect(self, hwnd: int) -> tuple:
        """获取窗口矩形区域"""
        rect = wintypes.RECT()
        if self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return (0, 0, 0, 0)
    
    def _is_valid_window(self, hwnd: int) -> bool:
        """检查是否为有效窗口"""
        if not self.user32.IsWindowVisible(hwnd):
            return False
        title = self._get_window_title(hwnd)
        if not title:
            return False
        # 排除系统窗口
        if self.user32.GetWindowLongW(hwnd, -20) == -8:  # WS_EX_TOOLWINDOW
            return False
        return True
    
    def get_all_windows(self) -> list:
        """获取所有窗口列表"""
        windows = []
        
        # 构建锁定查找表: key=(进程名,标题) -> (hwnd, info)
        # 用于窗口关闭再打开后的匹配
        locked_lookup = {}
        for hwnd, info in list(self._locked_windows.items()):
            key = (info.process_name.lower(), info.title.lower())
            locked_lookup[key] = (hwnd, info)
        
        @self.EnumWindowsProcType
        def enum_callback(hwnd, lParam):
            try:
                if self._is_valid_window(hwnd):
                    rect = self._get_window_rect(hwnd)
                    title = self._get_window_title(hwnd)
                    process_name = self._get_process_name(hwnd)
                    process_path = self._get_process_path(hwnd)
                    
                    # 先检查是否通过 hwnd 直接锁定
                    locked = hwnd in self._locked_windows
                    locked_size = None
                    locked_pos = None
                    
                    if locked:
                        locked_size = self._locked_windows[hwnd].locked_size
                        locked_pos = self._locked_windows[hwnd].locked_pos
                    else:
                        # 窗口关闭再打开后 hwnd 会变
                        # 通过进程名+标题匹配锁定状态
                        key = (process_name.lower(), title.lower())
                        if key in locked_lookup:
                            old_hwnd, old_info = locked_lookup[key]
                            # 检查旧 hwnd 是否已无效（窗口已关闭）
                            if not self.user32.IsWindow(old_hwnd):
                                locked = True
                                locked_size = old_info.locked_size
                                locked_pos = old_info.locked_pos
                                # 迁移到新 hwnd
                                self._locked_windows[hwnd] = old_info
                                self._locked_windows[hwnd].hwnd = hwnd
                                del self._locked_windows[old_hwnd]
                    
                    # 检查是否已置顶（hwnd 或 key 匹配）
                    pinned = hwnd in self._pinned_windows or self._is_window_pinned_by_key(process_name, title)
                    
                    info = WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        process_name=process_name,
                        process_path=process_path,
                        rect=rect,
                        locked=locked,
                        locked_size=locked_size,
                        locked_pos=locked_pos,
                        pinned=pinned
                    )
                    windows.append(info)
            except:
                pass
            return True
        
        try:
            self.user32.EnumWindows(enum_callback, wintypes.LPARAM(0))
        except:
            pass
        return windows
    
    def get_foreground_window(self) -> Optional[WindowInfo]:
        """获取当前前台窗口"""
        hwnd = self.user32.GetForegroundWindow()
        if hwnd and self._is_valid_window(hwnd):
            rect = self._get_window_rect(hwnd)
            title = self._get_window_title(hwnd)
            process_name = self._get_process_name(hwnd)
            process_path = self._get_process_path(hwnd)
            
            locked = hwnd in self._locked_windows
            locked_size = None
            locked_pos = None
            
            if not locked:
                # 尝试通过进程名+标题匹配
                key = (process_name.lower(), title.lower())
                for old_hwnd, old_info in list(self._locked_windows.items()):
                    if (old_info.process_name.lower(), old_info.title.lower()) == key:
                        if not self.user32.IsWindow(old_hwnd):
                            locked = True
                            locked_size = old_info.locked_size
                            locked_pos = old_info.locked_pos
                            # 迁移到新 hwnd
                            self._locked_windows[hwnd] = old_info
                            self._locked_windows[hwnd].hwnd = hwnd
                            del self._locked_windows[old_hwnd]
                        break
            else:
                locked_size = self._locked_windows[hwnd].locked_size
                locked_pos = self._locked_windows[hwnd].locked_pos
            
            return WindowInfo(
                hwnd=hwnd,
                title=title,
                process_name=process_name,
                process_path=process_path,
                rect=rect,
                locked=locked,
                locked_size=locked_size,
                locked_pos=locked_pos
            )
        return None
    
    def lock_window(self, hwnd: int) -> bool:
        """锁定指定窗口的当前位置和大小"""
        try:
            if not self.user32.IsWindow(hwnd):
                return False
            
            if self.user32.IsIconic(hwnd):
                return False
            
            rect = self._get_window_rect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            
            if width <= 0 or height <= 0:
                return False
            
            # 保存原始窗口样式，并尝试移除可调整大小的样式
            GWL_STYLE = -16
            WS_THICKFRAME = 0x00040000
            WS_MAXIMIZEBOX = 0x00010000
            
            original_style = self.user32.GetWindowLongW(hwnd, GWL_STYLE)
            style_lock_applied = False
            
            if original_style != 0 and (original_style & WS_THICKFRAME):
                new_style = original_style & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX
                set_result = self.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
                if set_result != 0:
                    style_lock_applied = True
                    # 触发框架重绘
                    SWP_FRAMECHANGED = 0x0020
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOZORDER = 0x0004
                    SWP_NOACTIVATE = 0x0010
                    self.user32.SetWindowPos(
                        wintypes.HWND(hwnd),
                        wintypes.HWND(0),
                        0, 0, 0, 0,
                        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                    )
                    logger.debug(f"已应用样式锁定: hwnd={hwnd:#x}, style={original_style:#x} -> {new_style:#x}")
            
            self._locked_windows[hwnd] = WindowInfo(
                hwnd=hwnd,
                title=self._get_window_title(hwnd),
                process_name=self._get_process_name(hwnd),
                rect=rect,
                locked=True,
                locked_size=(width, height),
                locked_pos=(rect[0], rect[1])
            )
            
            # 保存原始样式以便解锁时恢复
            self._locked_windows[hwnd].original_style = original_style if style_lock_applied else None
            
            return True
        except Exception as e:
            logger.error(f"锁定窗口失败: {e}", exc_info=True)
            return False
    
    def unlock_window(self, hwnd: int) -> bool:
        """解锁指定窗口"""
        if hwnd in self._locked_windows:
            info = self._locked_windows[hwnd]
            
            # 恢复原始窗口样式
            if hasattr(info, 'original_style') and info.original_style is not None:
                try:
                    GWL_STYLE = -16
                    self.user32.SetWindowLongW(hwnd, GWL_STYLE, info.original_style)
                    # 触发框架重绘
                    SWP_FRAMECHANGED = 0x0020
                    SWP_NOMOVE = 0x0002
                    SWP_NOSIZE = 0x0001
                    SWP_NOZORDER = 0x0004
                    SWP_NOACTIVATE = 0x0010
                    self.user32.SetWindowPos(
                        wintypes.HWND(hwnd),
                        wintypes.HWND(0),
                        0, 0, 0, 0,
                        SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                    )
                    logger.debug(f"已恢复窗口样式: hwnd={hwnd:#x}, style={info.original_style:#x}")
                except Exception as e:
                    logger.error(f"恢复窗口样式失败: {e}")
            
            del self._locked_windows[hwnd]
            return True
        return False
    
    def is_window_locked(self, hwnd: int) -> bool:
        """检查窗口是否已锁定"""
        if hwnd in self._locked_windows:
            return True
        # 尝试通过进程名+标题匹配
        try:
            title = self._get_window_title(hwnd)
            process_name = self._get_process_name(hwnd)
            key = (process_name.lower(), title.lower())
            for old_hwnd, old_info in list(self._locked_windows.items()):
                if (old_info.process_name.lower(), old_info.title.lower()) == key:
                    return True
        except:
            pass
        return False
    
    def get_locked_windows(self) -> list:
        """获取所有已锁定的窗口列表"""
        result = []
        to_remove = []
        for hwnd, info in list(self._locked_windows.items()):
            try:
                if self.user32.IsWindow(hwnd):
                    info.rect = self._get_window_rect(hwnd)
                    info.title = self._get_window_title(hwnd)
                    result.append(info)
                else:
                    to_remove.append(hwnd)
            except:
                to_remove.append(hwnd)
        for hwnd in to_remove:
            if hwnd in self._locked_windows:
                del self._locked_windows[hwnd]
        return result
    
    def _diagnose_window(self, hwnd: int) -> str:
        """诊断窗口属性，返回诊断信息字符串"""
        try:
            style = self.user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            ex_style = self.user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            is_visible = self.user32.IsWindowVisible(hwnd)
            is_iconic = self.user32.IsIconic(hwnd)
            is_zoomed = self.user32.IsZoomed(hwnd)
            is_window = self.user32.IsWindow(hwnd)
            rect = self._get_window_rect(hwnd)
            
            WS_THICKFRAME = 0x00040000
            WS_DLGFRAME = 0x00400000
            WS_CAPTION = 0x00C00000
            WS_POPUP = 0x80000000
            WS_OVERLAPPED = 0x00000000
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_TOPMOST = 0x00000008
            
            info = [
                f"hwnd={hwnd:#x}",
                f"IsWindow={is_window}",
                f"Visible={is_visible}",
                f"Iconic={is_iconic}",
                f"Zoomed={is_zoomed}",
                f"rect={rect}",
                f"style={style:#x}",
                f"  THICKFRAME(可调整大小)={bool(style & WS_THICKFRAME)}",
                f"  CAPTION={bool(style & WS_CAPTION)}",
                f"  DLGFRAME={bool(style & WS_DLGFRAME)}",
                f"  POPUP={bool(style & WS_POPUP)}",
                f"ex_style={ex_style:#x}",
                f"  TOPMOST={bool(ex_style & WS_EX_TOPMOST)}",
                f"  TOOLWINDOW={bool(ex_style & WS_EX_TOOLWINDOW)}",
            ]
            return " | ".join(info)
        except Exception as e:
            return f"诊断失败: {e}"
    
    def enforce_locked_windows(self):
        """强制执行所有锁定窗口的大小和位置"""
        to_remove = []
        to_update = {}  # old_hwnd -> new_hwnd
        
        # 先收集当前所有可见窗口，用于匹配
        current_windows = []
        
        @self.EnumWindowsProcType
        def collect_callback(hwnd, lParam):
            try:
                if self._is_valid_window(hwnd):
                    current_windows.append(hwnd)
            except:
                pass
            return True
        
        try:
            self.user32.EnumWindows(collect_callback, wintypes.LPARAM(0))
        except:
            pass
        
        # 构建当前窗口的查找表: key=(进程名,标题) -> hwnd
        current_lookup = {}
        for hwnd in current_windows:
            try:
                title = self._get_window_title(hwnd)
                process_name = self._get_process_name(hwnd)
                key = (process_name.lower(), title.lower())
                current_lookup[key] = hwnd
            except:
                pass
        
        # 处理每个锁定的窗口
        for hwnd, info in list(self._locked_windows.items()):
            try:
                if not self.user32.IsWindow(hwnd):
                    # 窗口已关闭，查找匹配的新窗口
                    key = (info.process_name.lower(), info.title.lower())
                    logger.debug(f"锁定窗口 hwnd={hwnd} 已无效，尝试匹配: {key}")
                    logger.debug(f"当前可用窗口: {list(current_lookup.keys())}")
                    if key in current_lookup:
                        new_hwnd = current_lookup[key]
                        to_update[hwnd] = new_hwnd
                        logger.debug(f"找到匹配的新窗口: {new_hwnd}")
                    else:
                        # 尝试仅通过进程名匹配（标题可能变化）
                        process_only_matches = []
                        for k, v in current_lookup.items():
                            if k[0] == info.process_name.lower():
                                process_only_matches.append((k, v))
                        if process_only_matches:
                            # 如果只有一个匹配，直接使用
                            if len(process_only_matches) == 1:
                                new_hwnd = process_only_matches[0][1]
                                to_update[hwnd] = new_hwnd
                                logger.debug(f"通过进程名匹配找到新窗口: {new_hwnd}")
                            else:
                                logger.debug(f"进程名匹配到多个窗口，跳过: {process_only_matches}")
                    continue
                
                if info.locked_size and info.locked_pos:
                    if self.user32.IsIconic(hwnd):
                        logger.debug(f"窗口 {info.title} 处于最小化状态，跳过")
                        continue
                    
                    rect = self._get_window_rect(hwnd)
                    cur_width = rect[2] - rect[0]
                    cur_height = rect[3] - rect[1]
                    
                    width, height = info.locked_size
                    left, top = info.locked_pos
                    
                    # 允许一定的误差（1像素），避免无限循环微调
                    width_diff = abs(cur_width - width)
                    height_diff = abs(cur_height - height)
                    x_diff = abs(rect[0] - left)
                    y_diff = abs(rect[1] - top)
                    
                    if width_diff > 1 or height_diff > 1 or x_diff > 1 or y_diff > 1:
                        logger.debug(f"窗口 {info.title} 需要调整: 当前({cur_width}x{cur_height}@{rect[0]},{rect[1]}) -> 目标({width}x{height}@{left},{top})")
                        
                        SWP_NOZORDER = 0x0004
                        SWP_NOACTIVATE = 0x0010
                        SWP_FRAMECHANGED = 0x0020
                        flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                        
                        result = self.user32.SetWindowPos(
                            wintypes.HWND(hwnd),
                            wintypes.HWND(0),
                            left, top, width, height,
                            flags
                        )
                        logger.debug(f"SetWindowPos 结果: {result}")
                        
                        if result == 0:
                            last_error = self.kernel32.GetLastError()
                            logger.debug(f"SetWindowPos 失败，错误码: {last_error}")
                            
                            # 首次失败时输出诊断信息
                            if not hasattr(self, '_diagnosed_windows'):
                                self._diagnosed_windows = set()
                            if hwnd not in self._diagnosed_windows:
                                logger.debug(f"窗口诊断: {self._diagnose_window(hwnd)}")
                                self._diagnosed_windows.add(hwnd)
                            
                            # 备用方案1: MoveWindow
                            move_result = self.user32.MoveWindow(
                                wintypes.HWND(hwnd),
                                left, top, width, height,
                                True
                            )
                            logger.debug(f"MoveWindow 结果: {move_result}")
                            
                            # 备用方案2: SetWindowPlacement (更可靠)
                            if move_result == 0:
                                try:
                                    wp = WINDOWPLACEMENT()
                                    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
                                    wp.showCmd = 1  # SW_SHOWNORMAL
                                    wp.rcNormalPosition.left = left
                                    wp.rcNormalPosition.top = top
                                    wp.rcNormalPosition.right = left + width
                                    wp.rcNormalPosition.bottom = top + height
                                    wp_result = self.user32.SetWindowPlacement(
                                        wintypes.HWND(hwnd),
                                        ctypes.byref(wp)
                                    )
                                    logger.debug(f"SetWindowPlacement 结果: {wp_result}")
                                except Exception as wp_err:
                                    logger.debug(f"SetWindowPlacement 异常: {wp_err}")
                    else:
                        logger.debug(f"窗口 {info.title} 大小位置已正确")
            except Exception as e:
                logger.error(f"处理锁定窗口出错: {e}", exc_info=True)
        
        # 更新 hwnd 映射
        for old_hwnd, new_hwnd in to_update.items():
            if old_hwnd in self._locked_windows:
                old_info = self._locked_windows.pop(old_hwnd)
                old_info.hwnd = new_hwnd
                self._locked_windows[new_hwnd] = old_info
                logger.debug(f"迁移锁定: {old_hwnd} -> {new_hwnd}")

                # 检查旧窗口是否置顶过，如有则对新窗口自动恢复置顶
                try:
                    was_pinned = (
                        old_hwnd in self._pinned_windows
                        or self._is_window_pinned_by_key(old_info.process_name, old_info.title)
                    )
                    if was_pinned and self.user32.IsWindow(new_hwnd):
                        self._pinned_windows.discard(old_hwnd)
                        self._pinned_windows.add(new_hwnd)
                        HWND_TOPMOST = wintypes.HWND(-1)
                        SWP_NOMOVE = 0x0002
                        SWP_NOSIZE = 0x0001
                        SWP_SHOWWINDOW = 0x0040
                        pin_result = self.user32.SetWindowPos(
                            wintypes.HWND(new_hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                        )
                        if pin_result:
                            logger.debug(f"迁移后自动恢复置顶: {old_hwnd} -> {new_hwnd}")
                        else:
                            logger.warning(f"迁移后置顶失败: {new_hwnd:#x}")
                except Exception as pin_err:
                    logger.debug(f"迁移后置顶异常: {pin_err}")

                # 重新应用样式锁定
                try:
                    GWL_STYLE = -16
                    WS_THICKFRAME = 0x00040000
                    WS_MAXIMIZEBOX = 0x00010000
                    current_style = self.user32.GetWindowLongW(new_hwnd, GWL_STYLE)
                    if current_style != 0 and (current_style & WS_THICKFRAME):
                        new_style = current_style & ~WS_THICKFRAME & ~WS_MAXIMIZEBOX
                        set_result = self.user32.SetWindowLongW(new_hwnd, GWL_STYLE, new_style)
                        if set_result != 0:
                            old_info.original_style = current_style
                            SWP_FRAMECHANGED = 0x0020
                            SWP_NOMOVE = 0x0002
                            SWP_NOSIZE = 0x0001
                            SWP_NOZORDER = 0x0004
                            SWP_NOACTIVATE = 0x0010
                            self.user32.SetWindowPos(
                                wintypes.HWND(new_hwnd),
                                wintypes.HWND(0),
                                0, 0, 0, 0,
                                SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
                            )
                            logger.debug(f"迁移后重新应用样式锁定: hwnd={new_hwnd:#x}")
                except Exception as style_err:
                    logger.debug(f"迁移后样式锁定失败: {style_err}")
                
                # 立即对新窗口执行锁定
                try:
                    if old_info.locked_size and old_info.locked_pos and self.user32.IsWindow(new_hwnd):
                        if not self.user32.IsIconic(new_hwnd):
                            width, height = old_info.locked_size
                            left, top = old_info.locked_pos
                            SWP_NOZORDER = 0x0004
                            SWP_NOACTIVATE = 0x0010
                            SWP_FRAMECHANGED = 0x0020
                            flags = SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED
                            self.user32.SetWindowPos(
                                wintypes.HWND(new_hwnd),
                                wintypes.HWND(0),
                                left, top, width, height,
                                flags
                            )
                except:
                    pass
        
        # 清理长时间无效的锁定条目
        # 如果窗口已关闭超过一定时间，可以选择移除
        # 这里暂时保留，让用户手动解锁
    
    def find_window_by_title(self, title: str) -> Optional[WindowInfo]:
        """根据标题查找窗口"""
        for window in self.get_all_windows():
            if title.lower() in window.title.lower():
                return window
        return None
    
    def pin_window(self, hwnd: int) -> bool:
        """置顶指定窗口"""
        try:
            if not self.user32.IsWindow(hwnd):
                return False
            HWND_TOPMOST = wintypes.HWND(-1)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            result = self.user32.SetWindowPos(
                wintypes.HWND(hwnd), HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )
            if result:
                self._pinned_windows.add(hwnd)
                # 同时保存 key 用于 hwnd 变化后的恢复
                try:
                    key = (self._get_process_name(hwnd).lower(), self._get_window_title(hwnd).lower())
                    self._pinned_keys.add(key)
                except:
                    pass
                logger.debug(f"置顶成功: hwnd={hwnd:#x}")
                return True
            else:
                err = ctypes.get_last_error() if hasattr(ctypes, 'get_last_error') else 0
                logger.warning(f"SetWindowPos 置顶失败: hwnd={hwnd:#x}, err={err}")
                return False
        except Exception as e:
            logger.error(f"置顶窗口异常: {e}", exc_info=True)
            return False
    
    def unpin_window(self, hwnd: int) -> bool:
        """取消置顶指定窗口"""
        try:
            if not self.user32.IsWindow(hwnd):
                return False
            HWND_NOTOPMOST = wintypes.HWND(-2)
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040
            result = self.user32.SetWindowPos(
                wintypes.HWND(hwnd), HWND_NOTOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )
            self._pinned_windows.discard(hwnd)
            # 同时移除 key
            try:
                key = (self._get_process_name(hwnd).lower(), self._get_window_title(hwnd).lower())
                self._pinned_keys.discard(key)
            except:
                pass
            if result:
                logger.debug(f"取消置顶成功: hwnd={hwnd:#x}")
                return True
            return False
        except Exception as e:
            logger.error(f"取消置顶异常: {e}", exc_info=True)
            return False
    
    def is_window_pinned(self, hwnd: int) -> bool:
        """检查窗口是否已置顶"""
        if hwnd in self._pinned_windows:
            return True
        # 兼容 hwnd 变化后的判定
        try:
            return self._is_window_pinned_by_key(
                self._get_process_name(hwnd), self._get_window_title(hwnd)
            )
        except Exception:
            return False
    
    def _is_window_pinned_by_key(self, process_name: str, title: str) -> bool:
        """通过进程名+标题检查窗口是否已置顶"""
        return (process_name.lower(), title.lower()) in self._pinned_keys
