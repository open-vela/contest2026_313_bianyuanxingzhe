# logs/ — AI Coding 日志目录

按[《AI Coding 日志归集与提交手册》](https://github.com/open-vela/docs/blob/dev-ai-contest-2026/zh-cn/contest_2026/ai_coding_log_guide.md)存放，与作品代码一并提交。

## 本队当前布局

```text
logs/
└── zixuanzheng2007-stack/
    ├── manifest.json
    ├── SOURCE_NOTE.md
    ├── 2026-07-19/
    ├── 2026-08-06/
    ├── 2026-09-01/
    ├── 2026-09-08/
    └── 2026-09-14/
```

| session_id | 内容 |
|------------|------|
| `6e5f1783-58c7-482e-8811-248998f1ee8c` | openvela 母目录：竞赛硬件资料与选型 |
| `c06c0b41-3b5e-4e46-a14d-1a09679677b2` | 专属仓 fork / 分支确认 |
| `df773b3a-7f00-4cb4-a0df-96892eb25e81` | 方案文档、VM/SSH、LD2451 接线 |
| `15467f1e-a3c1-4835-9802-8f43db4984b6` | 真机联调、屏显蜂鸣、WiFi UI、Agent Skill |
| `81d85e8a-bfe3-44be-b301-430c1b5adf8d` | 代码推送与远程仓库 |
| `527e9d06-d10e-4229-88aa-b522c584ff93` | 提交材料与文档整理 |

重导：`python scripts/archive_cursor_logs.py`

## 字段说明

每行 JSON 遵循手册 `schema_version: 1.0`（`role` / `text` / `tool_name` / `seq` 等）。  
`raw/` 为 Cursor Agent 原始 `.jsonl`。
