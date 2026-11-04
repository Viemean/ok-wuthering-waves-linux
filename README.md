# OK-WW (Linux / Proton Edition)

鸣潮自动化辅助工具（Linux / Steam Proton 兼容移植版）。

---

## 快速上手

### 1. 运行前提

- **系统环境**：Linux（Wayland / XWayland / X11）
- **Python 工具链**：[uv](https://docs.astral.sh/uv/)（推荐）或 Python >= 3.12
- **画面捕获组件（推荐）**：`obs-vkcapture`（提供 Vulkan 捕获；若未安装则自动回退至 X11 抓帧）
  ```bash
  # Arch Linux / Manjaro
  sudo pacman -S obs-vkcapture

  # Fedora
  sudo dnf install obs-vkcapture
  ```

### 2. 游戏启动配置

为了让辅助程序能够直接读取游戏画面的 Vulkan 交换链，运行游戏时需注入环境变量：

- **Steam 启动选项**：
  在游戏属性 -> 通用 -> 启动选项中填入：
  ```bash
  OBS_VKCAPTURE=1 %command%
  ```
- **Heroic / Lutris / 自定义启动脚本**：
  在游戏环境变量设置中添加 `OBS_VKCAPTURE=1`。

> 若直接在辅助程序界面中点击“启动游戏”，程序会自动附加该环境变量。

### 3. 克隆与运行

```bash
# 1. 克隆仓库（包含子模块）
git clone --recurse-submodules git@github.com:Viemean/ok-wuthering-waves-linux.git
cd ok-wuthering-waves-linux

# 2. 启动程序
uv run main.py
```

---

## 项目架构与技术文档

鸣潮自动化业务逻辑（战斗策略、地图导航、任务调度）位于 `src/`；Linux 平台底层跨平台驱动（Vulkan 画面捕获、Wine/Proton 后台输入代理、PipeWire 音频控制）由独立子模块提供。

底层技术实现与项目移植方法参阅以下文档：

- **底层框架实现**：[ok/README.md](ok/README.md)
- **通用自动化项目 Linux 移植实操指南**：[ok/docs/porting_guide.md](ok/docs/porting_guide.md)

---

## 上游与开源协议

- **官方原项目**：[ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
- **官方底层基座**：[ok-oldking/ok-script](https://github.com/ok-oldking/ok-script)
- 游戏内核心业务逻辑、角色招式识别与界面设计版权均归原作者及社区贡献者所有。

---

## 免责声明

- 本软件为外部辅助工具，仅通过图像识别与输入模拟运行，不读取游戏内存，不修改任何游戏文件或网络数据包。
- 严禁利用第三方工具破坏游戏公平性，使用本工具的潜在风险需由使用者自行承担。
- 本软件开源免费，仅供学习与技术交流使用，请勿用于商业目的。
