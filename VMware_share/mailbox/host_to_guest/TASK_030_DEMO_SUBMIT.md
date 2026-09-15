# TASK_030 · Demo 录像 + 队友收尾（截止 9/20）

**签发**: Host · 2026-09-15  
**优先级**: P0  
**回执**: `guest_to_host/REPLY_030_DEMO.md`（王/韦填真机段；郑填视频路径）

## 已完成（无需重复）

- PR #6 已合 `dev-ai-contest-2026`（代码 + logs + LICENSE）
- Skill `approach-warn` 已在 `ew_agent.c`

## 郑子轩 P0（Host）

1. 按 `docs/提交材料/Demo脚本与验收步骤.md` 录 ≤5min →  
   `docs/提交材料/边缘行者-Demo-contest2026_313_bianyuanxingzhe.mp4`
2. 拍 4 张照片 → `docs/提交材料/photos/`（见 README）
3. Word 定稿技术报告 → 覆盖 PDF 同名文件
4. `python scripts/pack_submission.py --check-only` → 齐件后 `python scripts/pack_submission.py` → 上传官网 zip

## 王筠昊 P0

- `host_smoke` ALL PASS 截图 → REPLY_030
- 技术报告 3.5 补 **1 行真机靠近数据**（距离/响应时间）

## 韦政宇 P0

- 真机 `ew fake 10 20` → 串口 `[ew_agent]` + `[alert_output]` 截图 → REPLY_030

## Guest 同步

```bash
cd ~/openvela/contest2026_313_bianyuanxingzhe
git fetch openvela dev-ai-contest-2026
git checkout dev-ai-contest-2026 || git checkout -b dev-ai-contest-2026 openvela/dev-ai-contest-2026
git pull openvela dev-ai-contest-2026
ls logs/zixuanzheng2007-stack/
# 王筠昊：确认 logs/wjh669939-cmd/ 若仍缺则按 docs/提交材料/Logs提取提示词_发给队友.md 补归档
```
