# 操作记录

## 2026-05-08

- 读取 `AGENTS.md` 和 HyperFrames / HyperFrames CLI / GSAP 技能说明，确认项目约束与视频 composition 规则。
- 检索 `README.zh.md` 与 `README.md`，确认主线命令为 `npm install -g mimo2codex`、`mimo2codex --version`、设置 `MIMO_API_KEY`、启动代理和打印配置。
- 复制用户提供的四张图片到 `tutorial-video/assets/`，作为教程视频素材。
- 尝试运行 `npx hyperframes --version`，在沙箱内 30 秒未返回，后续校验阶段会再次运行并按需申请放行。
- 创建 `tutorial-video/index.html`、`DESIGN.md` 和 `script.md`，实现 28 秒横版中文教程视频。
- 运行 HyperFrames lint，修复重复媒体发现警告。
- HyperFrames 默认浏览器下载缓存损坏，清理后仍下载失败；改用系统 Chrome 路径 `HYPERFRAMES_BROWSER_PATH` 完成 inspect、validate 和 render。
- 修复最终页 checklist 溢出问题，并让隐藏场景移出画布，减少无关审计噪声。
- 输出最终视频 `tutorial-video/renders/mimo2codex-npm-install-tutorial.mp4`。
