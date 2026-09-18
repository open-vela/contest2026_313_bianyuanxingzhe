# logs/ — AI Coding 日志目录

按[《AI Coding 日志归集与提交手册》](https://github.com/open-vela/docs/blob/dev-ai-contest-2026/zh-cn/contest_2026/ai_coding_log_guide.md)存放，与作品代码一并提交。

## 本队当前布局

```text
logs/
├── zixuanzheng2007-stack/   # 郑子轩（Host）· 8 会话（7 Cursor + 1 Codex）
└── wjh669939-cmd/           # 王筠昊（Guest VM Cursor Agent）· 6 会话
```

`wjh669939-cmd/` 含 `manifest.json`、`SOURCE_NOTE.md`，以及 2026-08-11 / 08-15 / 08-29 / 09-11 / 09-13。官方 `contest-snapshot --source cursor` 在 Guest 为 0 条，已按 Agent transcript 转 schema 1.0 并保留 `raw/`。

Host 会话一览（`zixuanzheng2007-stack/`）：

| session_id | 内容 |
|------------|------|
| `6e5f1783-58c7-482e-8811-248998f1ee8c` | openvela 母目录：竞赛硬件资料与选型 |
| `c06c0b41-3b5e-4e46-a14d-1a09679677b2` | 专属仓 fork / 分支确认 |
| `df773b3a-7f00-4cb4-a0df-96892eb25e81` | 方案文档、VM/SSH、LD2451 接线 |
| `15467f1e-a3c1-4835-9802-8f43db4984b6` | 真机联调、屏显蜂鸣、WiFi UI、Agent Skill |
| `81d85e8a-bfe3-44be-b301-430c1b5adf8d` | 代码推送与远程仓库 |
| `527e9d06-d10e-4229-88aa-b522c584ff93` | 提交材料与文档整理 |
| `f21b17e9-cd2b-475c-80ca-c2edb717282f` | PR#6 合入、pack 脚本、提交材料推进（2026-09-15） |
| `01a0b20d-669b-7502-9e56-9fc0dc3502d7` | WiFi/MiMo、PC 控制面板、显示交互与真机验收（Codex Desktop，2026-09-18） |

Cursor 重导：`python scripts/submission/archive_cursor_logs.py`

Codex Desktop 增量归档：`python scripts/submission/archive_codex_logs.py <session-id> --title <title>`。
官方 collector 1.3.0 的 Codex CLI 解析器暂不能识别 Desktop 的分页 rollout，兼容脚本沿用 schema 1.0、脱敏规则和不可覆盖策略。

## 字段说明

每行 JSON 遵循手册 `schema_version: 1.0`（`role` / `text` / `tool_name` / `seq` 等）。  
`raw/` 为 Cursor Agent 原始 `.jsonl`。
