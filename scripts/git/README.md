# Git · push 前 rebase

## 启用（每人一次）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/git/setup_hooks.ps1
```

## 手动 rebase

```bash
bash scripts/git/pre_push_rebase.sh
git push origin <branch>   # rebase 后可能需要 --force-with-lease
```

## 冲突惯例

- 保留 feature 的 `docs/` 子目录结构（`方案/` `硬件/` `烧录/`）
- 路径用 `scripts/submission/pack_submission.py`，不要根目录旧路径
- 不要恢复 `VMware_share/mailbox/`
- 提交清单：合并 upstream 的 PR/待办状态 + feature 的新路径

冲突后：`git add` → `git rebase --continue`
