# 分析上下文

## 仓库基线

- Fork：`xtayjmh/CapsWriter-Offline`
- 上游：`HaujetZhao/CapsWriter-Offline`
- 基线分支：`master`
- 工作分支：`agent/dynamic-island-pipeline`

## 关键调用链

1. `core/client/shortcut/task.py`：快捷键启动、取消和结束一次录音任务。
2. `core/client/audio/recorder.py`：生成任务 ID、发送音频分片和最终消息。
3. `core/client/output/result_processor.py`：接收最终识别结果、热词处理、LLM 路由和输出。
4. `core/client/output/text_output.py`：键盘写入或剪贴板粘贴的最终落点。
5. `core/client/app.py`：客户端组件创建与停止顺序。
6. `build.spec`、`build-client.spec`、`zip_release.py`：完整包、纯客户端包和 ZIP 分发。

## 设计结论

- 状态 UI 必须内置客户端，才能可靠收到输出完成事件。
- 状态 UI、状态总线和动画全部由 `CapsWriterClient` 创建与释放，不启动独立辅助进程。
- 状态总线使用线程安全队列；UI 独立线程消费，不跨线程直接操作 Tk。
- 状态关联使用任务 ID；旧任务的迟到结果不能覆盖新任务 UI。
- 快捷键录音状态带显示延迟，短按只切换大小写。
- 现有重连和识别算法保持不变，“管线增强”限定为生命周期事件、关联、容错和可测试性。
- uv 只负责可复现环境和构建编排，最终可执行文件仍由项目现有 PyInstaller 生成。
- uv 属于维护者构建流程；最终用户仍然只运行 `start_client.exe`。
