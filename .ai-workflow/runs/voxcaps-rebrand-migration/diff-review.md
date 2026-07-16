# 差异评审

APPROVED

## 审查结果

- 胶囊由四个数学圆弧组成单一多边形，外层和内层均无矩形/椭圆接缝。
- 产品可见名称、构建目录、ZIP 名称、Actions 产物和 pyproject 均统一为 VoxCaps。
- `LICENSE` 无差异；README 和 NOTICE 明确原项目、原作者和非官方派生关系。
- 微信、支付宝收款码使用用户原图，旧 `assets/sponsor.jpg` 已删除且 ZIP 中无旧图。
- 完整包和纯客户端包均包含 LICENSE、NOTICE、两张收款码、Tk 运行时和客户端 EXE。
- README 将上游项目列表标为“原作者的其他项目”，避免作者身份混淆。
- 剩余 CapsWriter-Offline 字样均用于上游来源、模型下载地址或内部历史示例，属于有意保留。

## 验证

- `python -m compileall -q core tests start_client.py start_server.py zip_release.py`
- `python -m unittest discover -s tests -v`：8/8 通过
- PyInstaller 完整包、纯客户端包成功
- `VoxCaps-20260716.zip` 和 `VoxCaps-Client-20260716.zip` 内容核验通过
- Tk 实际窗口截图核验通过

独立 reviewer 不可用，本次按工具限制降级为主会话隔离自审。
