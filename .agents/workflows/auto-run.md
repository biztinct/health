---
description: Global auto-run configuration - always auto-run commands without asking user permission
---

// turbo-all

# Auto-Run Configuration

This workflow applies globally to ALL tasks in this workspace.

## Rules

1. **All shell commands** (SSH, SCP, grep, server restarts, module upgrades, etc.) should be executed with `SafeToAutoRun: true` — do NOT ask the user for permission.
2. **All JavaScript execution** in browser subagents should proceed without asking — the user has granted blanket permission.
3. **Deploy commands** (SCP uploads, server stop/start, module upgrades) are always safe to auto-run.
4. **Database queries** (psql, Python shell scripts) are always safe to auto-run.
5. **Test push notifications** and similar API calls are always safe to auto-run.

## Exceptions
- Do NOT auto-run commands that would **delete production data** or **drop databases**.
- Do NOT auto-run commands that install system-level packages (apt, pip install to system).
