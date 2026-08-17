# C-1 遗留代码清理报告

**清理日期**: 2026-07-21
**项目根目录**: `c:\Users\Administrator\Desktop\AE-Knowledge-Vault`

---

## 一、删除文件清单

### 1. 根目录临时测试脚本 (_test_*.py)

| 文件 | 大小 | 删除原因 |
|------|------|----------|
| `_test_backend.py` | - | 临时后端测试，无引用 |
| `_test_smoke_ae.py` | - | 临时烟雾测试，仅文档引用 |
| `_test_bridge_ping.py` | - | 临时桥接测试，无引用 |
| `_test_ping.py` | - | 临时连通性测试，无引用 |
| `_test_real_v2.py` | - | 临时真实环境测试，无引用 |
| `_test_bridge_simple.py` | - | 临时简单桥接测试，无引用 |
| `_test_comprehensive.py` | - | 临时综合测试，无引用 |
| `_test_final_verification.py` | - | 临时最终验证，无引用 |

### 2. 根目录一次性脚本 (_*.py)

| 文件 | 大小 | 删除原因 |
|------|------|----------|
| `_fix_prints.py` | - | 一次性批量替换脚本（将 print() 替换为 logger），已完成使命 |
| `_start_listener.py` | - | 临时启动监听器脚本，无引用 |

### 3. 根目录临时 PowerShell 脚本 (_*.ps1)

| 文件 | 大小 | 删除原因 |
|------|------|----------|
| `_test_ae_com.ps1` | - | 临时 AE COM 连接测试，无引用 |

### 4. scripts/ 目录临时诊断脚本

| 文件 | 大小 | 删除原因 |
|------|------|----------|
| `scripts/check_latest_log.ps1` | - | 临时日志诊断脚本，无引用 |
| `scripts/cleanup_admin.ps1` | - | 临时管理员清理脚本，无引用 |
| `scripts/cleanup_admin_v2.ps1` | - | 临时管理员清理脚本 v2，无引用 |
| `scripts/compare_fonts.ps1` | - | 临时字体对比脚本，无引用 |
| `scripts/deep_diagnosis_v3.ps1` | - | 临时深度诊断脚本，无引用 |
| `scripts/codex_start.bat` | - | 临时启动脚本，无引用 |

**删除总计**: 17 个文件

---

## 二、保留文件清单

### 1. 根目录保留的临时脚本

| 文件 | 保留原因 | 引用位置 |
|------|----------|----------|
| `_import_redirect.py` | 导入重定向工具，被多个模块使用 | `load_listener_manual.py`, `load_and_test_bridge.py`, `_verify_ehi.py`, `_test_e2_ae.py` |
| `_verify_ehi.py` | EHI 阶段全量验证脚本，重要测试资产 | 无代码引用，但作为阶段验证脚本保留 |
| `_test_e2_ae.py` | 端到端测试，被执行流程引用 | `pipeline/stages/execution.py` |

### 2. 根目录保留的部署/运维脚本 (*.bat, *.ps1)

| 文件 | 保留原因 |
|------|----------|
| `deploy.bat` | 部署脚本 |
| `deploy_mcp_panel.bat` | MCP 面板部署 |
| `deploy_opensource_panel.bat` | 开源面板部署 |
| `install_listener.bat` | 监听器安装 |
| `copy_scripts_to_ae.bat` | AE 脚本复制 |
| `add_defender_exclusions.bat` | Defender 排除配置 |
| `disable_plugins_admin.bat` | 插件禁用 |
| `clear_startup_admin.bat` | 启动项清理 |
| `cleanup_ae_scripts.bat` | AE 脚本清理 |
| `emergency_remove_panel.bat` | 紧急移除面板 |
| `update_bridge_2026.bat` | Bridge 升级 |
| `run_rebuild.bat` | 重建脚本 |
| `启动Codex.bat` | Codex 启动 |
| `switch_ae_to_english.bat` | AE 语言切换 |
| `install_adobe_bridges.ps1` | Adobe Bridge 安装 |
| `D盘AE脚本管理器.ps1` | 脚本管理工具 |

### 3. bridges/ 目录保留

| 文件 | 保留原因 |
|------|----------|
| `bridges/ae_mcp_client.py` | 被 `pipeline/stages/execution.py`、`load_listener_manual.py`、`load_and_test_bridge.py` 引用 |
| `bridges/ae_bridge_base.py` | 被 `bridges/ae_mcp_client.py` 引用 |
| `bridges/adobe_bridge_adapter.py` | 被 `bridges/pr_bridge_client.py` 等引用 |
| `bridges/pr_bridge_client.py` | 被 `bridges/adobe_bridge_adapter.py` 引用 |
| `bridges/ps_bridge_client.py` | 被 `bridges/adobe_bridge_adapter.py` 引用 |
| `bridges/au_bridge_client.py` | 被 `bridges/adobe_bridge_adapter.py` 引用 |
| `bridges/adobe_mcp_manager.py` | 可能被其他模块使用 |
| `bridges/adobe_mcp_server.py` | 可能被其他模块使用 |
| `bridges/adobe_open_source_integration.py` | 可能被其他模块使用 |
| `bridges/adobe_suite_integration.py` | 可能被其他模块使用 |
| `bridges/adobe_universal_bridge.py` | 可能被其他模块使用 |
| `bridges/mcp_bridge_client.py` | 可能被其他模块使用 |
| `bridges/opencut_bridge.py` | 可能被其他模块使用 |
| `bridges/unified_bridge_base.py` | 可能被其他模块使用 |

> **说明**: `bridges/` 目录中的旧实现目前仍被核心代码引用，暂不删除。新的 `ae/adapters/` 架构正在逐步替代旧实现，但尚未完全迁移。

### 4. ae/ 目录保留

| 文件 | 保留原因 |
|------|----------|
| `ae/ae_mcp_client.py` | 主 MCP 客户端，被 `ae/adapters/mcp_adapter.py` 引用 |
| `ae/adapters/mcp_adapter.py` | 新适配器架构，统一接口 |
| `ae/adapters/puppet_adapter.py` | 新适配器架构，Puppet 风格 |
| `ae/bridge_protocol.py` | 协议定义，被 `ae/ae_mcp_client.py` 引用 |
| `ae/bridge_middleware.py` | 中间件管道，被 `ae/ae_mcp_client.py` 引用 |
| `ae/bridge_health.py` | 健康检查 |
| `ae/bridge_maintenance.py` | 维护工具 |
| `ae/bridge_transport.py` | 传输层 |

---

## 三、清理说明

### 清理原则

1. **无引用优先**: 完全无代码引用的临时脚本优先删除
2. **文档引用不视为有效引用**: 仅在文档中提及的文件视为可清理
3. **阶段验证脚本保留**: `_verify_ehi.py` 作为阶段验证脚本保留
4. **部署脚本保留**: 所有部署相关的 `.bat`/`.ps1` 脚本保留
5. **核心代码引用保留**: 被核心模块引用的文件保留

### 未清理项说明

1. **bridges/ 目录**: 虽然 `ae/adapters/` 提供了新架构，但旧的 `bridges/` 模块仍被 `pipeline/stages/execution.py` 等核心代码引用，需后续逐步迁移
2. **scripts/ 目录**: 大部分脚本仍可能被手动使用，仅删除明显的临时诊断脚本

### 后续建议

1. 逐步迁移 `bridges/` 目录中的功能到 `ae/adapters/` 架构
2. 定期清理 `scripts/` 目录中的临时测试脚本
3. 建立 `.gitignore` 规则，防止临时测试文件提交

---

## 四、统计

| 类别 | 删除数 | 保留数 |
|------|--------|--------|
| 根目录 `_test_*.py` | 8 | 2 |
| 根目录 `_*.py` (非测试) | 2 | 1 |
| 根目录 `_*.ps1` | 1 | 0 |
| scripts/ 目录 | 6 | - |
| **总计** | **17** | - |