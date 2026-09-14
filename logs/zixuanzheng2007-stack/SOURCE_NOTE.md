# Cursor → 竞赛 logs 归档说明

- 官方采集工具：Claude Code / OpenCode / Codex / AIoT-IDE（需 openvela `.repo/` 工作区 + install.sh）
- 本目录日志来源：Cursor Agent transcripts（含 `e:\openvela` 母目录会话）
- `cursor__*.jsonl`：已映射为手册 schema_version 1.0
- `raw/*.jsonl`：Cursor 原始文件，未改内容
- 生成方式：`python scripts/archive_cursor_logs.py`（collection_mode = manual-cursor-archive）
- 2026-09 补档：`15467f1e`（真机/UI/WiFi/Skill）、`81d85e8a`、`527e9d06`；`df773b3a` 全量重导至 8/25
- 能力覆盖矩阵见同目录 **`COVERAGE.md`**（供评审快速核对，避免误判缺失）
- GitHub：zixuanzheng2007-stack · team_id = contest2026_313_bianyuanxingzhe
