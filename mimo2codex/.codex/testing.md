# 测试记录

## HyperFrames

- `npx --yes hyperframes lint tutorial-video`
  - 结果：通过，0 errors，0 warnings。
- `HYPERFRAMES_BROWSER_PATH="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" npx --yes hyperframes inspect tutorial-video --json --samples 8`
  - 结果：通过，0 errors，0 warnings。
  - 备注：通用抽样在 12.25s 转场点报告了 off-canvas info，属于 push slide 转场的预期状态。
- `HYPERFRAMES_BROWSER_PATH="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" npx --yes hyperframes inspect tutorial-video --json --at 2,8.5,15,20.5,26`
  - 结果：通过，稳定帧 0 issues。
- `HYPERFRAMES_BROWSER_PATH="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" npx --yes hyperframes validate tutorial-video`
  - 结果：0 errors，0 warnings；仍有 16 条 contrast warnings，集中在深色命令块/截图 callout 的采样上。
- `HYPERFRAMES_BROWSER_PATH="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" npx --yes hyperframes render tutorial-video --output tutorial-video/renders/mimo2codex-npm-install-tutorial.mp4 --quality standard --workers 1`
  - 结果：渲染成功，输出 MP4 文件。

## 环境备注

- 默认 HyperFrames Chrome Headless Shell 下载源返回了损坏包，报错 `end of central directory record signature not found`。
- 已改用本机 Chrome：`C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe`。
- 当前 PowerShell PATH 中没有 `ffmpeg` / `ffprobe` 命令；HyperFrames 内部可完成渲染，但无法额外用外部 `ffprobe` 做媒体信息检查。
