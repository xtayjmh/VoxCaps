# VoxCaps

![demo](assets/demo.png)

> **按住 CapsLock 说话，松开就上屏。就这么简单。**

**VoxCaps** 是一个专为 Windows 打造的本地优先语音输入工具，支持客户端内置动态状态岛、局域网服务端和离线模型。

## 项目说明

本项目基于 [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) 二次开发。感谢原作者 Haujet Zhao 提供离线语音识别、客户端/服务端通信、热词和文本处理等核心能力。

VoxCaps 不是原项目的官方发行版。原项目版权和 MIT License 均完整保留，详细来源见 [NOTICE.md](NOTICE.md)。在原仓库基础上，VoxCaps 3.x 主要增加和调整了：

- **客户端内置灵动岛**：无需额外脚本，以琥珀、青蓝、紫色分别反馈麦克风准备、录音和识别状态，成功或失败后立即隐藏；
- **CapsLock 按需麦克风**：启动只预热一次，空闲不持续占用；短按保持大小写功能，长按超过 250 毫秒才进入语音输入，并保留开头音频；
- **连续口述顺序送达**：允许上一段识别时继续录制，结果严格按录音顺序上屏；
- **独立 VoxCaps 品牌**：统一窗口、托盘、客户端和服务端 EXE 的多尺寸 Windows 图标；
- **可复现双包发布**：提供客户端+服务端完整包与纯客户端包，并自动检查测试、版本、图标和 ZIP 内容一致性；
- **使用说明增强**：补充局域网客户端、麦克风权限、灵动岛状态，以及中文语境夹英文单词的模型选择建议。

## ✨ 核心特性

-   **语音输入**：按住 `CapsLock键` 或 `鼠标侧键X2` 说话，松开即输入，超低延迟，默认去除末尾逗句号。支持对讲机模式和单击录音模式。
-   **文件转录**：音视频文件往客户端 exe 一丢，字幕 (`.srt`)、文本 (`.txt`)、时间戳 (`.json`) 统统都有。
-   **数字 ITN**：自动将「十五六个」转为「15~16个」，支持各种复杂数字格式。
-   **热词替换**：在 `hot.txt` 记下偏僻词，通过音素模糊匹配，相似度大于阈值则强制替换。
-   **正则替换**：在 `hot-rule.txt` 用正则或简单等号规则，精准强制替换。
-   **LLM 角色**：预置了润色、小助理等角色，当识别结果的开头匹配任一角色名字时，将交由该角色处理。
-   **托盘菜单**：右键托盘图标即可添加热词、复制结果、清除LLM记忆。
-   **动态状态岛**：随客户端自动启动，以琥珀、青蓝和紫色分别提示准备、录音和识别；成功或失败后立即隐藏，不显示绿色完成或红色错误动画。
-   **C/S 架构**：服务端与客户端分离，虽然 Win7 老电脑跑不了服务端模型，但最少能用客户端输入。
-   **日记归档**：按日期保存你的每一句语音及其识别结果。
-   **录音保存**：所有语音均保存为本地音频文件，隐私安全，永不丢失。

**VoxCaps** 保留完全离线、低延迟、高准确率和高度自定义的核心体验，同时增强了录音、识别、送达和异常状态的桌面反馈。

以下为支持的模型：

| 引擎名 | 准确性 | 中文夹英文 | 速度 | 格式 | 显卡加速 |
|------|-------|-----------|------|------|---------|
| Paraformer | ★★★☆☆ | 较弱 | ★★★★★ | ONNX | ❌ |
| SenseVoice-Small | ★★★☆☆ | 一般 | ★★★★★ | ONNX | ✅ |
| Fun-ASR-Nano | ★★★★☆ | 较好 | ★★★★☆ | ONNX + GGUF | ✅ |
| Qwen3-ASR | ★★★★★ | 最好 | ★★★☆☆ | ONNX + GGUF | ✅ |

“中文夹英文”指中文句子中混说英文单词、缩写和技术术语时的相对表现。这里给出的是基于模型语言覆盖和实际使用特征的经验性分级，并非同一测试集上的百分比基准；口音、麦克风、语速、上下文和热词都会影响结果。Paraformer 更适合纯中文和常见词；SenseVoice-Small 能处理中英混说，但生僻技术词仍可能不稳定；Fun-ASR-Nano 在速度与中英文混合准确率之间较均衡，并可通过 `config_client.py` 的 `context` 补充人名、产品名和专业术语；Qwen3-ASR 的多语言和上下文能力最强，但资源占用也最高。


性能参考（20s 音频转录延迟）：

| 模型 | CPU U9-285H | GPU RTX5050 |
|------|------------|------------|
| Paraformer | 0.6s | - |
| SenseVoice-Small | 0.6s | 0.15s |
| Fun-ASR-Nano | 2.0s | 0.5s |
| Qwen3-ASR-1.7B | 4.0s | 1.0s |

详细功能说明请参考 [`docs/`](docs/) 目录：
- [环境依赖安装说明](docs/环境依赖安装说明.md) — VC++ 运行库、FFmpeg 安装
- [热词功能如何使用](docs/热词功能如何使用.md) — 热词替换、规则替换、自定义短语
- [角色功能如何使用](docs/角色功能如何使用.md) — LLM 角色配置、输出模式、创建新角色
- [识别语言如何配置](docs/识别语言如何配置.md) — 各引擎语言支持范围与配置方法
- [文件转录功能如何使用](docs/文件转录功能如何使用.md) — 拖拽转字幕、时间戳对齐
- [显卡加速的若干问题](docs/显卡加速的若干问题.md) — DirectML、Vulkan 加速配置
- [模型下载的若干问题](docs/模型下载的若干问题.md) — 引擎选择、模型下载、目录结构
- [常见问题](docs/常见问题.md) — FAQ
- [动态状态岛与 UV 双包构建](docs/动态状态岛与UV双包构建.md) — 状态说明、自定义尺寸、维护者构建
- [更新日志](docs/CHANGELOG.md) 


## 💻 平台支持

目前**仅能保证在 Windows 10/11 (64位) 下完美运行**。

- **Linux**：暂无环境进行测试和打包，无法保证兼容性。
- **MacOS**：由于底层的 `keyboard` 库已放弃支持 MacOS，且系统限制极多，暂时无法支持。

[LazyTyper](https://lazytyper.com/) 和 [闪电说](https://shandianshuo.cn/) 也是很优秀的作品，都有离线引擎，都支持 Windows Linux 与 MacOS，并都有漂亮的图形化页面，推荐使用。

VoxCaps 的特别之处在于追求：

- 无感输入
- 完全离线，不受网络约束
- 低延迟，尽量做到硬件极限的最快速度
- 高度自定义的热词系统


## 🎬 快速开始

1.  **准备环境**：确保安装了 [VC++ 运行库](https://learn.microsoft.com/zh-cn/cpp/windows/latest-supported-vc-redist)。若要使用文件转录功能，还需安装 [ffmpeg](https://ffmpeg.org/download.html) 并确保其在系统 PATH 中。
2.  **下载解压**：下载 [VoxCaps Latest Release](https://github.com/xtayjmh/VoxCaps/releases/latest) 里的软件本体；模型仍从原项目的 [Models Release](https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models) 下载，解压到 `models` 文件夹中对应模型目录。
    Windows 完整包已经包含 Fun-ASR-Nano、Qwen3-ASR 等 GGUF 引擎所需的 llama.cpp Vulkan 运行库以及音频解码依赖，不需要另外寻找或复制 DLL；按模型目录说明放好模型后即可启动 Server。
3.  **启动服务**：双击 `start_server.exe`，**它会自动最小化到托盘菜单**。
4.  **启动听写**：双击 `start_client.exe`，**它会自动最小化到托盘菜单**。
5.  **开始录音**：按住 `CapsLock键` 或 `鼠标侧键X2` 就可以说话了！

### CapsLock 与麦克风行为

- `CapsLock` 是唯一的键盘语音触发键；右 Alt 和 AltGr 不被 VoxCaps 接管，保持 Windows 原有行为。
- 按住超过 250 毫秒才确认为语音输入；250 毫秒内松开属于短按，仍正常切换大小写。
- 按下 CapsLock 时会异步打开麦克风并暂存开头音频，因此短按时 Windows 麦克风指示可能短暂闪现；松开后会立即释放。
- 客户端启动约 1 秒后只预热一次麦克风，验证成功或失败后都会立即关闭；空闲时不会持续占用麦克风。
- 麦克风不可用时，客户端只提示检查 Windows 麦克风权限或安全软件设置，不会崩溃；下一次长按会自动重试。


## ⚙️ 个性化配置

所有的设置都在根目录的 `config_server.py` 和 `config_client.py` 里，可直接编辑。


## 🛠️ 常见问题


**Q: 为什么按了没反应？**  
A: 请确认 `start_client.exe` 的黑窗口还在运行。若想在管理员权限运行的程序中输入，也需以管理员权限运行客户端。

**Q: 为什么识别结果没字？**  
A: 到 `年/月/assets` 文件夹中检查录音文件，看是不是没有录到音；听听录音效果，是不是麦克风太差，建议使用桌面 USB 麦克风；检查麦克风权限。

**Q: 想要隐藏黑窗口？**  
A: 点击托盘菜单即可隐藏黑窗口。

**Q: 如何开机启动？**  
A: `Win+R` 输入 `shell:startup` 打开启动文件夹，将服务端、客户端的快捷方式放进去即可。

更多问题请参阅 [docs/常见问题.md](docs/常见问题.md)。


## 🚀 原作者的其他项目

以下项目来自 CapsWriter-Offline 原作者 Haujet Zhao：

| 项目名称 | 说明 | 体验地址 |
| :--- | :--- | :--- |
| [**IME_Indicator**](https://github.com/HaujetZhao/IME_Indicator) | Windows 输入法中英状态指示器 | [下载即用](https://github.com/HaujetZhao/IME_Indicator/releases/latest/download/IME-Indicator.exe) |
| [**Rust-Tray**](https://github.com/HaujetZhao/Rust-Tray) | 将控制台最小化到托盘图标的工具 | [下载即用](https://github.com/HaujetZhao/Rust-Tray/releases/latest/download/Tray.exe) |
| [**Gallery-Viewer**](https://github.com/HaujetZhao/Gallery-Viewer-HTML) | 网页端图库查看器，纯 HTML 实现 | [点击即用](https://haujetzhao.github.io/Gallery-Viewer-HTML/) |
| [**全景图片查看器**](https://github.com/HaujetZhao/Panorama-Viewer-HTML) | 单个网页实现全景照片、视频查看 | [点击即用](https://haujetzhao.github.io/Panorama-Viewer-HTML/) |
| [**图标生成器**](https://github.com/HaujetZhao/Font-Awesome-Icon-Generator-HTML) | 使用 Font-Awesome 生成网站 Icon | [点击即用](https://haujetzhao.github.io/Font-Awesome-Icon-Generator-HTML/) |
| [**五笔编码反查**](https://github.com/HaujetZhao/wubi86-revert-query) | 86 五笔编码在线反查 | [点击即用](https://haujetzhao.github.io/wubi86-revert-query/) |
| [**快捷键映射图**](https://github.com/HaujetZhao/ShortcutMapper_Chinese) | 可视化、交互式的快捷键映射图 (中文版) | [点击即用](https://haujetzhao.github.io/ShortcutMapper_Chinese/) |


## ❤️ 致谢

本项目基于以下优秀的开源项目：

-   [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
-   [FunASR](https://github.com/alibaba-damo-academy/FunASR)
-   [CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline)

同时感谢 CodeX 编程助手为本分支开发提供帮助。

## 支持 VoxCaps 分支维护

以下赞助仅用于支持 VoxCaps 分支新增功能的开发、测试和维护，不代表原项目作者收款。

| 微信支付 | 支付宝 |
| --- | --- |
| <img src="assets/sponsor-wechat.jpg" alt="VoxCaps 微信赞助" width="240"> | <img src="assets/sponsor-alipay.jpg" alt="VoxCaps 支付宝赞助" width="240"> |
