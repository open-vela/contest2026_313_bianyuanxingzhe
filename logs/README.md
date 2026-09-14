# logs/ — AI Coding 日志目录

按[《AI Coding 日志归集与提交手册》](https://github.com/open-vela/docs/blob/dev-ai-contest-2026/zh-cn/contest_2026/ai_coding_log_guide.md)存放，与作品代码一并提交。

## 本队当前布局

```text
logs/
└── zixuanzheng2007-stack/          # GitHub: zixuanzheng2007-stack
    ├── manifest.json               # 会话清单（6 会话）
    ├── COVERAGE.md                 # 评审用：时间线 + 能力覆盖说明
    ├── SOURCE_NOTE.md
    ├── 2026-07-19/  cursor__6e5f1783 + raw/
    ├── 2026-08-06/  cursor__c06c0b41, cursor__df773b3a + raw/
    ├── 2026-09-01/  cursor__15467f1e + raw/   # 真机联调主会话
    ├── 2026-09-08/  cursor__81d85e8a + raw/
    └── 2026-09-14/  cursor__527e9d06 + raw/
```

| session_id | 内容 |
|------------|------|
| `6e5f1783-58c7-482e-8811-248998f1ee8c` | openvela 母目录：竞赛硬件资料与选型 |
| `c06c0b41-3b5e-4e46-a14d-1a09679677b2` | 专属仓 fork / 分支确认 |
| `df773b3a-7f00-4cb4-a0df-96892eb25e81` | 方案文档、VM/SSH、LD2451 接线（至 8/25） |
| `15467f1e-a3c1-4835-9802-8f43db4984b6` | 真机：EW READY、蜂鸣、WiFi UI、host_smoke、ew_agent、PR#5 |
| `81d85e8a-bfe3-44be-b301-430c1b5adf8d` | 代码 push / 远程状态 |
| `527e9d06-d10e-4229-88aa-b522c584ff93` | 提交清单与 logs 合规（9/14） |

补档命令：`python scripts/archive_cursor_logs.py`

## 字段说明

转换后的每行 JSON 遵循手册 `schema_version: 1.0`（`role` / `text` / `tool_name` / `seq` 等）。  
额外字段 `source: cursor-agent-transcript` 标明来源。  
`raw/` 为未改动的 Cursor Agent 原始 `.jsonl`，便于核对。

## 重要合规提示

官方自动采集支持：**Claude Code / OpenCode / Codex / AIoT-IDE**（见手册 Q9）。  
**Cursor 不在官方自动采集列表**。本批为开发全过程手工归档，供评委追溯；`repo sync` 后请安装 `contest-log-collector`，后续优先用官方工具开发。

## 后续自动入仓（Ubuntu / Git Bash）

```bash
cd contest2026_313_bianyuanxingzhe
bash ../.claude/skills/contest-log-collector/onboarding/install.sh \
  --team-id contest2026_313_bianyuanxingzhe \
  --github-login zixuanzheng2007-stack
```

队友各自改 `GITHUB_LOGIN` 为自己的用户名，日志按账号分目录。
