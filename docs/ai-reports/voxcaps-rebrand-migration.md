# VoxCaps 更名、迁移与发布报告

## 结果

- 项目更名为 **VoxCaps**，远程仓库为 <https://github.com/xtayjmh/VoxCaps>。
- 原项目 `LICENSE` 保持不变；新增 `NOTICE.md` 说明来源、版权和派生功能。
- README 与发行包使用用户提供的微信、支付宝二维码，并明确为支持 VoxCaps 分支维护。
- 动态状态岛改为单一连续圆角轮廓，端部半径略小于半高，消除了圆形与矩形错位接缝。
- 全部近期提交已直接快进到 `master`；旧 PR 已被 GitHub 标记为已合并。
- `master` 已启用线性历史，并禁止强制推送和删除。
- 正式工作副本位于 `B:\VoxCaps`，上游仍指向 HaujetZhao/CapsWriter-Offline。
- Obsidian 项目主页位于 `01_Projects/VoxCaps/00-项目总览.md`。

## 验证

- `python -m unittest discover -s tests -v`：8 项通过。
- `python -m compileall -q core tests start_client.py start_server.py zip_release.py`：通过。
- 完整包与纯客户端包均完成 PyInstaller 构建和 ZIP 内容检查。
- 两个 ZIP 均包含 `LICENSE`、`NOTICE.md`、Tk 运行库和新赞助图片，不再包含旧 `assets/sponsor.jpg`。
- 实际 Tk 窗口截图确认状态岛外框连续、位于 Windows 可用工作区内。

## 发行文件

- `release/VoxCaps-20260716.zip`
- `release/VoxCaps-Client-20260716.zip`
