# mimo2codex 教程视频视觉规范

## Style Prompt

干净的技术教程视频，像开发者文档和终端录屏的混合体：明亮背景、清晰层级、少量高饱和橙色只用于安装命令和关键步骤。画面必须让观众第一眼看到 `npm install -g mimo2codex`，其余信息作为辅助证据出现。

## Colors

- 背景：`#E7ECEF`
- 主文字：`#1F2933`
- 次文字：`#52616B`
- 面板：`#FBFCF8`
- 边框：`#C9D3DA`
- 主强调：`#EE6C4D`
- 辅助蓝：`#274C77`
- 终端深色：`#18212B`

## Typography

- 标题：`LXGW WenKai Screen`, `PingFang SC`, sans-serif
- 正文：`Aptos`, `Microsoft YaHei`, sans-serif
- 命令/代码：`JetBrains Mono`, `Cascadia Mono`, monospace

## Motion

- 主要转场：横向 push slide，表现“下一步”。
- 主题切换：轻微 blur crossfade，用于从安装步骤转到实测结果。
- 每个场景都有入口动画，命令先出现，说明随后进入。

## What NOT to Do

- 不使用紫蓝渐变、霓虹光效或装饰性卡片堆叠。
- 不把所有截图等权摆放，安装截图和安装命令必须最大。
- 不在画面里讲太多背景，仓库介绍和 agent 实测只做短暂停留。
