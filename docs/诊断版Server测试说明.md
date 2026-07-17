# VoxCaps Server 诊断版测试说明

此诊断能力用于定位模型 Worker 启动后立即退出的问题。

## 使用方法

1. 把现有 Server 的模型目录复制到程序目录的 `models` 下，保持原目录层级不变；
2. 确认 `config_server.py` 中的 `model_type` 与要测试的模型一致；
3. 双击 `start_server.exe`；
4. 如果启动失败，请保留窗口，并收集以下文件：
   - `logs/server_latest.log`
   - `logs/worker_crash_latest.log`
   - `logs/worker_native_crash_latest.log`

`worker_crash_latest.log` 会记录完整 Python Traceback、DLL 实际加载结果、ONNX Provider、显卡与驱动信息。`worker_native_crash_latest.log` 用于记录 Vulkan、驱动或其他原生库崩溃时的最后调用栈。
