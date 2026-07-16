# CapsWriter 动态状态岛上下文

本改造为客户端增加可关闭的进程内状态岛。状态来源必须是实际业务事件，不通过猜测键盘状态或监听日志实现。

最终用户只启动 `start_client.exe`；状态岛随客户端自动启动并在客户端退出时释放，不需要任何辅助命令。

状态顺序：

```text
idle -> recording -> recognizing -> delivered -> idle
                              \-> error -> idle
```

构建仍使用上游 PyInstaller spec；uv 负责准备环境并编排完整包、纯客户端包和 ZIP 生成。
