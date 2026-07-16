# 动态状态岛与 UV 双包构建

## 使用方式

动态状态岛已经集成进 `start_client`：启动客户端时自动启动，退出客户端时自动释放，不需要运行额外脚本或后台程序。

状态含义：

- 青蓝波形：正在录音；
- 紫色光点：服务端正在识别，或客户端正在处理结果；
- 绿色流光：文字已经成功送达当前输入位置；
- 红色提示：连接或发送过程发生异常。

短按 CapsLock 切换大小写时，状态岛不会出现。客户端会等待一小段时间，确认进入有效录音后再显示。

## 配置

在 `config_client.py` 的 `ClientConfig` 中调整：

```python
dynamic_island_enabled = True       # 是否启用
dynamic_island_width = 276          # 宽度（最小 96）
dynamic_island_height = 68          # 高度（最小 26）
dynamic_island_bottom_margin = 18   # 距 Windows 可用工作区底边的距离
dynamic_island_hold_delay_ms = 180  # 按住多久后显示
```

这些配置只影响客户端界面，不改变服务端模型或识别协议。界面初始化失败时，客户端会记录警告并继续提供语音输入。

## 识别管线增强

一次语音输入从按键按下开始就获得唯一任务 ID。录音、识别、文字输出和送达动画使用同一 ID；如果较早任务的结果延迟到达，状态岛会忽略它，避免旧结果覆盖新任务的状态。

## 使用 UV 构建双包

维护者在 Windows PowerShell 中运行：

```powershell
./scripts/build-windows-packages.ps1
```

脚本使用 `uv.lock` 创建可复现环境，并依次生成：

- `CapsWriter-Offline`：Client + Server 完整包；
- `CapsWriter-Offline-Client`：只含 Client 的局域网客户端包。

ZIP 文件输出到 `release`。本机需要 Python 和 uv；若尚未安装 uv，可运行 `python -m pip install uv`。ZIP 使用 Python 标准库生成，不再依赖 7-Zip。普通用户不需要安装 uv，直接使用发布页中的 ZIP 即可。

GitHub Actions 工作流 `.github/workflows/windows-packages.yml` 也支持手动触发，或在推送 `v*` 标签时构建并上传两个产物。
