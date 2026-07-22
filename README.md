# 窗口锁定工具 WindowLocker

一款 Windows 桌面窗口管理工具，支持锁定窗口大小、窗口置顶、持久化锁定。使用 Python + tkinter 开发，启动快、体积小。

## 功能特性

- **窗口大小锁定** - 锁定任意窗口的当前尺寸，防止被意外调整
- **持久化锁定** - 窗口关闭后重新打开，只要工具运行即可自动恢复锁定状态（独家功能）
- **窗口置顶** - 将任意窗口置顶显示在最前方
- **左右分栏展示** - 左侧未锁定窗口列表，右侧已锁定窗口列表
- **真实应用图标** - 自动获取并显示每个窗口的真实应用图标
- **系统托盘常驻** - 最小化到托盘，后台持续运行
- **标题栏拖拽** - 按住标题栏可自由移动工具窗口

## 截图

> 可在此处添加工具运行截图

## 环境要求

- Windows 10 / 11
- Python 3.10+

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourname/WindowLocker.git
cd WindowLocker

# 安装依赖
pip install -r requirements.txt
```

## 使用

```bash
python main.py
```

### 操作说明

1. 工具启动后，左侧列表显示当前所有未锁定的窗口
2. 选中一个窗口，点击「锁定/解锁」按钮，窗口移动到右侧已锁定列表
3. 锁定后窗口大小将被固定，关闭再打开仍保持锁定
4. 点击「置顶/取消」按钮可将选中窗口置顶显示
5. 点击右上角关闭按钮会最小化到系统托盘，右键托盘图标可退出

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller window_locker.spec
```

打包完成后，可执行文件位于 `dist/WindowLocker/` 目录。

## 项目结构

```
window_locker/
├── main.py                  # 主程序入口（tkinter UI + 主逻辑）
├── requirements.txt         # Python 依赖
├── window_locker.spec       # PyInstaller 打包配置
├── core/
│   ├── __init__.py
│   └── window_manager.py    # 窗口管理核心（Windows API 封装）
├── ui/
│   ├── __init__.py
│   └── tray_app.py          # 系统托盘图标
└── README.md
```

## 技术栈

- **UI 框架** - tkinter (Python 内置)
- **窗口管理** - Windows API (ctypes)
- **系统托盘** - [pystray](https://github.com/moses-palmer/pystray)
- **图标处理** - [Pillow](https://python-pillow.org/)

## 开源协议

[MIT License](LICENSE)
