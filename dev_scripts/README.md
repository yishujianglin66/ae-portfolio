# dev_scripts/ — 手动 Harness 说明

本目录下的 `test_*.py` 文件**不是 pytest 单元测试**。

它们是「手动验收 harness」：运行时向真实 Adobe 软件（AE / PR / 等）的
MCP Bridge 写入命令 JSON（如 `~/Documents/ae-mcp-bridge/ae_command.json`），
由真实软件拾取执行。因此：

- **不进 CI**：`pytest` 的 `testpaths` 指向 `tests/`，本目录不在其中，不会被收集。
- **需真实环境**：必须在真实 AE/PR 运行时、且 Bridge 就绪后，手动
  `python dev_scripts/test_xxx.py` 执行。
- **不可被 pytest 误收集**：若被 pytest 收集，会因顶层 `sys.exit` / 写文件 /
  等待 AE 响应而中断整套件。（`tests/conftest.py` 的忽略逻辑只覆盖 `tests/` 内，
  不覆盖本目录。）

与之对比，`tests/` 下才是真正的 pytest 套件（含 P0 冒烟测试
`test_p0_imports.py`、`test_mcp_config.py`）。

CI 运行方式：

```bash
uv run --no-project python -m pytest
```
