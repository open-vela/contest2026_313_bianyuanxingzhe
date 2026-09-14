# AI Coding 日志覆盖说明（供评审）

队伍 **边缘行者** · GitHub `zixuanzheng2007-stack` · 工具 **Cursor Agent**（手工转 schema 1.0 + 保留 `raw/`）

## 会话时间线（无断档）

| 时段 | session_id | 开发内容 |
|------|------------|----------|
| 2026-07-19 | `6e5f1783` | openvela 母目录：竞赛资料、DevKit 选型 |
| 2026-08-06 | `c06c0b41` | 专属仓 fork / 分支确认 |
| 2026-08-06 — 08-25 | `df773b3a` | 方案文档、VM/SSH、mailbox 协作、LD2451 接线、屏显/触摸调试 |
| 2026-09-01 — 09-13 | `15467f1e` | **主会话**：EW READY、蜂鸣、三页 UI、WiFi AT/UI、host_smoke、ew_agent / approach-warn、PR#5 |
| 2026-09-08 | `81d85e8a` | 代码 push、远程分支与 CLA 状态 |
| 2026-09-14 | `527e9d06` | 提交材料清单、logs 合规分析与补档 |

**说明**：2026-08-26 — 08-31 期间本机无新增 Cursor 会话（该周主要为 VM 内编译/烧录与线下联调）；9/1 会话直接延续同一仓库开发，代码演进见 git history（如 `91ea733` LD2451 解析路径）。

## 能力环节 ↔ 日志证据

| 环节 | 负责人 | 主要 session | 关键词（可在 jsonl 内检索） |
|------|--------|--------------|----------------------------|
| 立项 / 硬件选型 | 郑子轩 | `6e5f1783` | DevKit-LCD、LD2451、竞赛 |
| 仓结构 / 分支 | 郑子轩 | `c06c0b41` | fork、dev-ai-contest-2026 |
| 方案 + VM 协作编排 | 郑子轩 | `df773b3a` | VMware、mailbox、SSH、LD2451 接线 |
| LD2451 解析 + 策略 | 王筠昊 | `df773b3a`、`15467f1e` | `ew_ld2451`、`host_smoke` |
| 屏显 / 触摸 / 蜂鸣 | 郑子轩 | `df773b3a`、`15467f1e` | `alert_buzzer`、`lvgldemo`、`fb0`、FT6146 |
| 三页 UI + WiFi | 郑子轩 | `15467f1e` | `ew_wifi`、`nuttx_wifiui`、WiFi UI |
| ai_agent Skill | 韦政宇 | `15467f1e` | `ew_agent`、`approach-warn`、`approach_alert` |
| 合入 / push | 郑子轩 | `81d85e8a`、`15467f1e` | PR#5、dev-ai-contest-2026 |
| 提交合规 | 郑子轩 | `527e9d06` | logs、manifest、上交材料 |

## 客观限制（已在技术报告 / 分工文档说明）

1. **单 GitHub 账号归档**：三人共用 Host Cursor + Guest VM 流水线；Guest 侧独立 Cursor 会话（若存在）未单独入 `logs/`，协作过程在 `df773b3a` / `15467f1e` 的 mailbox / SSH 编排对话中有记录。
2. **Cursor 非官方自动采集工具**（手册 Q9）：本队全程使用 Cursor；已手工映射为 schema 1.0，并保留 `raw/*.jsonl` 原始 transcript 供核对。转换版中 tool 的 `output` 字段为占位（完整工具回包见 raw）。
3. **未纳入本仓的 transcript**：`f45f0548`（其他项目 ShenZhi 日志走查，与本届作品无关）、`a98e4701`（空会话/额度错误，无有效对话）。

## 完整性自检

```powershell
# manifest 条目数 = 6；各 file 行数 = manifest.event_count
python scripts/archive_cursor_logs.py   # 从本机 transcript 重导，应全部 OK

# 关键能力检索示例（15467f1e 主会话）
# Select-String -Path logs\...\cursor__15467f1e*.jsonl -Pattern "host_smoke|ew_agent|approach-warn"
```

清单索引：`logs/zixuanzheng2007-stack/manifest.json`
