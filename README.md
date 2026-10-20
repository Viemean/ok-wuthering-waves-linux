# OK-WW (Linux / Proton Edition)

> OK-WW —— Linux / Steam Proton 兼容移植版。

---

### 上游项目

本项目是基于原作者 **[@ok-oldking](https://github.com/ok-oldking)** 的开源项目二次开发的 Linux 移植分支：

* **官方原项目仓库**：[ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
* **官方底层框架**：[ok-oldking/ok-script](https://github.com/ok-oldking/ok-script)
* **官方项目网站**：[https://ok-script.com/ok-ww](https://ok-script.com/ok-ww)

鸣潮游戏内的核心业务逻辑、角色招式识别与界面设计版权均归原作者及社区贡献者所有。感谢原作者与开源社区的贡献。

请注意，根据库洛官方的《鸣潮》公平运营声明：
> 严禁利用任何第三方工具破坏游戏体验。
> 我们将严厉打击使用外挂、加速器、作弊软件、宏脚本等违规工具的行为，这些行为包括但不限于自动挂机、技能加速、无敌模式、瞬移、修改游戏数据等操作。
> 一经查证，我们将视违规情况和次数，采取包括但不限于扣除违规收益、冻结或永久封禁游戏账号等措施。

**使用本软件即表示您已阅读、理解并同意以上声明，并自愿承担一切潜在风险。**

---

### 可靠性

业余兴趣驱动的 Linux 移植分支，**不提供可靠性保证与长期维护承诺**
分支的更新节奏与功能稳定性无法与官方原版同步；同时因为平台底层差异过大，代码暂时独立维护，暂不向上游提交 PR。使用过程中遇到问题需自行排查与调试。

---

### 快速开始

#### 1. 运行环境

* **Proton**：dwproton
* **显示服务**：XWayland / X11
* **Python 工具链**：[uv](https://docs.astral.sh/uv/)（默认 Python 3.14，或 >=3.12）

#### 2. 安装与启动

```bash
# 1. 克隆仓库（浅克隆）
git clone --depth=1 git@github.com:Viemean/ok-wuthering-waves-linux.git
cd ok-wuthering-waves-linux

# 2. 启动程序（uv 自动处理依赖环境）
uv run main.py
# 或直接运行
./main.py
```

---

### 适配实现

原版使用 Windows 专有 API（Win32、DirectX、COM）。Linux 运行环境下替换为对应的 Linux / POSIX 接口：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Linux 宿主环境 (Python 3.14 / Qt6)                   │
│                                                                        │
│                      ┌──────────────────────┐                          │
│                      │ 自动化任务调度核心   │                          │
│                      │  (TaskExecutor)      │                          │
│                      └──────────┬───────────┘                          │
│            ┌────────────────────┼────────────────────┐                 │
│            ▼                    ▼                    ▼                 │
│  ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐        │
│  │ 画面捕获子系统   │ │ 输入控制子系统   │ │ 音频控制子系统   │        │
│  │ (X11 MIT-SHM     │ │ (uinput 前台 /   │ │ (PulseAudio /    │        │
│  │  + OpenCV SIMD)  │ │  WineAgent 后台) │ │  PipeWire pactl) │        │
│  └────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘        │
└───────────┼────────────────────┼────────────────────┼──────────────────┘
            │ 共享内存抓帧       │ 127.0.0.1:49152    │ 动态音频流静音
            ▼                    ▼ (TCP IPC)          ▼
┌──────────────────────┐ ┌──────────────────────────────────────────────┐
│  显示合成服务        │ │        Proton / WinePrefix 虚拟环境            │
│  (XWayland / X11)    │ │                                              │
│                      │ │  ┌──────────────────────┐                    │
│                      │ │  │ ok-wine-agent.exe    │                    │
│                      │ │  │ (多线程 Win32 代理)  │                    │
│                      │ │  └──────────┬───────────┘                    │
│                      │ │             ▼ Win32 PostMessage + mouse_event│
│                      │ │  ┌──────────────────────┐                    │
│                      │ │  │ 鸣潮游戏本体 (UE4)   │                    │
│                      │ │  │ Client-Win64-Shipping│                    │
│                      │ │  └──────────────────────┘                    │
└──────────────────────┘ └──────────────────────────────────────────────┘
```

#### 实现对照

| 子系统 | Windows 接口 | Linux 适配接口 | 说明 |
| :--- | :--- | :--- | :--- |
| **画面捕获** | DXGI Desktop Duplication / WGC (D3D11) | `X11 MIT-SHM (XShmGetImage)` + `cv2.cvtColor` | 从 XWayland 共享内存段读取窗口 Framebuffer 并转换为 BGR |
| **后台按键输入** | Win32 `PostMessage` | Proton 内置 `ok-wine-agent.exe` (TCP 49152 IPC) | Wine 进程内部调用 `PostMessageW` 分发后台键鼠消息 |
| **前台按键输入** | `pydirectinput` / `mouse` | `/dev/uinput` 接口 | 向 Linux uinput 设备节点写入输入事件 |
| **后台动态静音** | Windows Core Audio COM (`pycaw`) | PulseAudio / PipeWire (`pactl`) | 依据窗口焦点变化查询游戏进程对应的 sink-input 并切换静音状态 |
| **环境依赖** | `requirements.txt` (含 Windows 专有包) | `requirements-linux.txt` | 移除 Windows 专有依赖包，运行时根据平台动态检测导入 |

#### 结构与架构差异

对比原版 [ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)，本分支的主要文件与架构变动如下：

1. **核心框架内联（多出 `ok/` 目录）**
   * **原版架构**：官方仓库仅包含游戏业务代码（`src/`），底层框架以 pip 依赖包形式引入 `ok-script`。由于 `ok-script` 强绑定 Windows 独占 API（`win32gui`、`pycaw`、`d3d11`、`pydirectinput`），无法在 Linux 上直接安装与运行。
   * **本分支架构**：将 `ok-script` 框架源码直接解耦并合并到项目内的 `ok/` 目录中，在框架内部完成跨平台抽象重构，实现运行时动态检测与模块按需加载。

2. **新增 Linux 原生底层子系统**
   * **`ok/device/capture_methods/linux_window.py` & `linux_capture.py`**：替代原版 Win32 / D3D11 截屏逻辑。使用 `python-xlib` 遍历 X11/XWayland 窗口树，通过 MIT-SHM（XShmGetImage 共享内存）实现零拷贝抓帧。
   * **`ok/device/audio_methods/linux_audio.py`**：替代原版 Windows Core Audio (`pycaw`)。基于 PipeWire / PulseAudio 原生协议（`pulsectl`），通过窗口焦点变化动态匹配游戏音频流（sink-input）实现后台自动静音。
   * **`ok/device/interaction_methods/linux_uinput.py`**：针对前台操作，基于 Linux 内核 `/dev/uinput` 接口创建硬件级虚拟键鼠，替代依赖 Windows 驱动的 `pydirectinput`。

3. **新增 Proton / Wine 辅助代理（`ok-wine-agent.exe`）**
   * **`ok/device/interaction_methods/linux_proton_post_message.py`**：负责与运行在 WinePrefix 内部的辅助代理通过本地 TCP（`127.0.0.1:49152`）通信。
   * **`ok-wine-agent.exe`**：部署在 Proton 环境内的轻量 Win32 代理进程，在 Wine 进程树内直接调用 `PostMessageW` 分发后台键鼠消息，避免跨越 Wine 边界造成的事件丢弃，实现无需夺取窗口焦点的后台静默控制。

4. **工程化与依赖规范变更**
   * **`requirements-linux.txt`**：移除 Windows 专属包，仅声明 Linux 运行环境所需的库。
   * **`.python-version` & `uv.lock`**：引入 uv 现代依赖管理，锁定 Python 3.14+ 运行时与依赖项

5. **业务调度逻辑微调**
   * **`src/combat/CombatCheck.py`**：适配 Proton 后台模式下的中键锁定怪逻辑，防止因消息时序引发的锁怪循环取消。
   * **`ok/task/TaskExecutor.py`**：优化任务中断逻辑，在状态等待循环中增加即时状态检查，点击停止按钮时由原先的 10 秒超时中断优化为毫秒级退出。

#### C 扩展源码说明

项目中包含两个 C 语言编写的底层扩展组件，源码均包含在仓库中：

1. **X11 共享内存抓帧扩展 (`ok-xshm-capture.so`)**
   * **源码位置**：`ok/device/capture_methods/xshm/xshm_capture.c`
   * **编译工具链**：`gcc`、`libX11`、`libXext`
   * **编译命令**：

     ```bash
     gcc -O3 -fPIC -shared ok/device/capture_methods/xshm/xshm_capture.c -lX11 -lXext -o ok/device/capture_methods/bin/ok-xshm-capture.so
     ```

   * **说明**：程序首次运行时若未检测到 `.so` 动态库，会尝试自动调用本地 `gcc` 编译；若宿主机未安装开发头文件，将降级至 `mss` 截图后端。

2. **Proton / Wine 后台代理程序 (`ok-wine-agent.exe`)**
   * **源码位置**：`ok/device/interaction_methods/wine_agent/main.c`
   * **编译工具链**：`mingw-w64`（`x86_64-w64-mingw32-gcc`）
   * **交叉编译命令**：

     ```bash
     x86_64-w64-mingw32-gcc -O2 -s -o ok/device/interaction_methods/bin/ok-wine-agent.exe ok/device/interaction_methods/wine_agent/main.c -lws2_32
     ```

   * **说明**：仓库中已预置编译产物，开箱即用，无需预先安装 MinGW 交叉编译器；仅在二次开发或修改 C 代理协议时需重新编译。

---

### 免责声明

* 本软件为外部辅助工具，仅通过纯图像识别与操作系统级键鼠模拟运行，不读取游戏内存，不修改任何游戏文件或网络数据包。
* 本软件开源、免费，仅供个人学习与交流使用，请勿用于任何商业或营利性目的。因使用本软件产生的任何问题，均与本项目及开发者无关。
