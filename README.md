# OK-WW (Linux / Proton Edition)

鸣潮自动化辅助工具（Linux / Steam Proton 兼容移植版）。

---

## 快速上手

### 1. 运行前提

- **系统环境**：Linux（Wayland / XWayland / X11）
- **Python 环境**：[uv](https://docs.astral.sh/uv/)（推荐）或 Python >= 3.12
- **画面捕获组件（推荐）**：`obs-vkcapture`（未安装时可回退至 `X11_Direct`）
  ```bash
  # Arch Linux / Manjaro
  sudo pacman -S obs-vkcapture

  # Fedora
  sudo dnf install obs-vkcapture
  ```

### 2. 游戏启动与系统配置

- **注入 `OBS_VKCAPTURE=1`**：
  - Steam 启动选项：`OBS_VKCAPTURE=1 %command%`
  - Heroic / Lutris / 自定义脚本：在游戏环境变量中添加 `OBS_VKCAPTURE=1`
- **Wayland 全局热键权限（可选）**：
  - 如需在 Wayland / `gamescope` 下使用 `F9`~`F12` 全局热键，建议将当前用户加入 `input` 用户组以启用 `evdev` 监听（无权限时会自动回退至 `pynput`）。

> 请先由启动器启动游戏，再在软件顶部栏连接弹窗中选择窗口、捕获与交互方式（`gamescope` 推荐 `Vulkan` + `libei`）。

### 3. 克隆与运行

```bash
git clone --recurse-submodules https://github.com/Viemean/ok-wuthering-waves-linux.git
cd ok-wuthering-waves-linux
uv run main.py
```

---

## 技术栈概览

- **业务层（`src/`）**：鸣潮战斗轴、日常清体力、声骸识别、地图传送与多账号任务调度；使用 OpenCV、ONNXRuntime / OpenVINO（ONNXOCR / YOLOv8）进行视觉与文字识别。
- **界面与框架（[ok/README.md](ok/README.md)）**：基于 PySide6（`ok.ui.qt.kit` 3.x 组件库）构建，底层由独立子模块 `ok-script-linux` 提供 Linux 画面捕获、键鼠交互与音频静音控制。

---

## 上游与版本说明

- **官方原项目**：[ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
- **官方底层基座**：[ok-oldking/ok-script](https://github.com/ok-oldking/ok-script)
- **UI 版本**：当前主分支基于 `ok-script 3.x`（纯 PySide6）；原 2.x（`PySide6-Fluent-Widgets`）最终状态归档于标签 `v2.x-ui-final`（`ok` 子模块为 `v2.x-linux-final`）。
- 游戏内核心业务逻辑、角色招式识别与界面设计版权归原作者及社区贡献者所有。

---

## 免责声明

- 本软件为外部辅助工具，仅通过图像识别与输入模拟运行，不读取游戏内存，不修改任何游戏文件或网络数据包。
- 严禁利用第三方工具破坏游戏公平性，使用本工具的潜在风险需由使用者自行承担。
- 本软件开源免费，仅供学习与技术交流使用，请勿用于商业目的。
