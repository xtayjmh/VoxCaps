# 实施计划

1. 将胶囊外框改为单个平滑圆角多边形，圆角半径使用高度的 44%，保留内外两层描边。
2. 采用 **VoxCaps** 品牌，更新 README、pyproject、PyInstaller 输出目录、ZIP 名称和 Actions 产物名。
3. 保留原 LICENSE，新增 NOTICE；README 首屏明确项目基于 HaujetZhao/CapsWriter-Offline 二次开发。
4. 将用户两张图片原样复制为 `assets/sponsor-wechat.jpg` 和 `assets/sponsor-alipay.jpg`，删除旧合成赞助图引用。
5. 增加/调整回归测试，运行 compileall、unittest、双包构建与 ZIP 内容核验。
6. 提交功能分支并直接快进 `master`，推送后关闭 Draft PR。
7. 将 GitHub 仓库改名为 `VoxCaps`，更新本地 remote；创建 `B:\VoxCaps` 克隆。
8. 对默认分支启用保护：禁止强推、禁止删除、要求线性历史；不强制 PR，以保留维护者直接推送方式。
9. 在 Obsidian `01_Projects/VoxCaps` 创建项目笔记，记录来源、功能、部署、路线与仓库链接。

## 回滚

- GitHub 仓库改名可改回；旧 URL 会自动重定向。
- 主分支保护可通过 API 删除或调整。
- 临时目录保留，不删除原工作副本；`B:\VoxCaps` 创建失败不影响现有仓库。
- 收款码替换前保留在 Git 历史中，可回滚提交恢复。
