# 作品展示照片（官网 zip 选交 / 技术报告插图）

命名建议（jpg/png，≥1280px 宽）：

| 文件 | 内容 |
|------|------|
| `01_正面.jpg` | DevKit-LCD + LD2451 + 蜂鸣器全貌 |
| `02_接线.jpg` | UART2 雷达线、PA28 蜂鸣、ESP AT 线清晰 |
| `03_预警橙.jpg` | 屏显 WARN 橙 + 蜂鸣响 |
| `04_预警红.jpg` | 屏显 CRIT 红（或 EW READY 蓝底对照） |

拍完后自检：`python scripts/pack_submission.py --check-only`  
齐 PDF + mp4 + photos 后：`python scripts/pack_submission.py`
