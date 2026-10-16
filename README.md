# OK-WW (Linux / Proton Edition)

> 鸣潮（Wuthering Waves）自动化辅助工具 —— Linux / Steam Proton 兼容移植版。

---

### 💖 致敬与上游项目

本项目是基于原作者 **[@ok-oldking](https://github.com/ok-oldking)** 的开源项目二次开发的 Linux 移植分支：

* **官方原项目仓库**：[ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)
* **官方底层框架**：[ok-oldking/ok-script](https://github.com/ok-oldking/ok-script)
* **官方项目网站**：[https://ok-script.com/ok-ww](https://ok-script.com/ok-ww)

鸣潮游戏内的核心业务逻辑、角色招式识别与界面设计版权均归原作者及社区贡献者所有。感谢原作者与开源社区的贡献。

---

### 🛠️ 平台适配实现

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

#### 子系统实现对照

| 子系统 | Windows 接口 | Linux 适配接口 | 说明 |
| :--- | :--- | :--- | :--- |
| **画面捕获** | DXGI Desktop Duplication / WGC (D3D11) | `X11 MIT-SHM (XShmGetImage)` + `cv2.cvtColor` | 从 XWayland 共享内存段读取窗口 Framebuffer 并转换为 BGR |
| **后台按键输入** | Win32 `PostMessage` | Proton 内置 `ok-wine-agent.exe` (TCP 49152 IPC) | Wine 进程内部调用 `PostMessageW` 分发后台键鼠消息，不移动光标且不夺取前台焦点 |
| **前台按键输入** | `pydirectinput` / `mouse` | `/dev/uinput` 接口 | 向 Linux uinput 设备节点写入输入事件 |
| **后台动态静音** | Windows Core Audio COM (`pycaw`) | PulseAudio / PipeWire (`pactl`) | 依据窗口焦点变化查询游戏进程对应的 sink-input 并切换静音状态 |
| **环境依赖** | `requirements.txt` (含 Windows 专有包) | `requirements-linux.txt` | 移除 Windows 专有依赖包，运行时根据平台动态检测导入 |

---

### 🚀 快速开始

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

### ⚠️ 免责声明

* 本软件为外部辅助工具，仅通过纯图像识别与操作系统级键鼠模拟运行，不读取游戏内存，不修改任何游戏文件或网络数据包。
* 本软件开源、免费，仅供个人学习与交流使用，请勿用于任何商业或营利性目的。因使用本软件产生的任何问题，均与本项目及开发者无关。
