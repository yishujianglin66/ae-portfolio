# AE 2025 崩溃根因诊断报告

**诊断日期**: 2026-07-21  
**AE 版本**: After Effects 2025 (25.3)  
**系统**: Windows 25H2

---

##  根本原因 (按可能性排序)

### 1. Windows Defender 实时保护拦截 (最可能)
**现象**: 
- Windows Defender 处于激活状态
- AE 文件夹和进程**未添加到白名单**
- AEHeadless.exe 文件缺失（可能被 Defender 误删）

**影响**: 
- Defender 可能将 AE 的某些组件识别为威胁并隔离/删除
- 实时扫描可能干扰 AE GUI 组件加载
- 导致启动后 11-18 秒崩溃

**解决方案**:
```powershell
# 以管理员身份运行 PowerShell
Add-MpPreference -ExclusionPath "C:\Program Files\Adobe\Adobe After Effects 2025"
Add-MpPreference -ExclusionPath "C:\Users\Administrator\AppData\Roaming\Adobe\After Effects"
Add-MpPreference -ExclusionProcess "AfterFX.exe"
```

---

### 2. AEHeadless.exe 关键组件缺失
**现象**:
```
[MISSING] AEHeadless.exe
```
**位置**: `C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AEHeadless.exe`

**影响**: 
- AEHeadless.exe 是 AE GUI 模式的核心组件
- 缺失会导致 GUI 无法初始化
- 命令行模式 (-r, -s) 不受影响（不需要此文件）

**解决方案**: 
- 重新安装 AE 会恢复此文件
- 安装后立即添加到 Defender 白名单防止再次被删

---

### 3. Windows 更新兼容性问题 (可能)
**最近更新的补丁** (2026-07-15):
- KB5100998 - Update
- KB5101650 - Security Update
- KB5120102 - Security Update

**影响**: 
- 某些安全更新可能影响 Adobe 软件兼容性
- 特别是涉及图形驱动或系统库的更新

**解决方案**:
- 如果重装后仍崩溃，尝试卸载这些更新
- 或等待 Adobe 发布兼容性修复

---

### 4. 第三方插件不兼容 (已排除)
**已禁用的问题插件**:
- FEC Presets 7 (多个特效插件)
- Element 3D 系列 (8 个插件)
- BlaceGPU (GPU 插件)
- RobuskeyMovie (GPU 抠像插件)

**状态**: 已重命名为 `.disabled`，不影响重装

---

### 5. Startup 脚本问题 (已解决)
**问题**: Startup 目录中的 JSX 脚本即使只有注释也会导致崩溃

**状态**: 
- 已删除所有第三方 Startup 脚本
- 备份中包含干净的监听器脚本

---

## ✅ 重装 AE 后的完整防护流程

### 步骤 1: 安装 AE 2025
- 使用 Adobe Creative Cloud 或安装包安装
- 安装完成后**先不要启动 AE**

### 步骤 2: 添加 Defender 白名单 (关键！)
**以管理员身份运行**:
```
C:\Users\Administrator\Desktop\AE-Knowledge-Vault\add_defender_exclusions.bat
```

或手动运行 PowerShell (管理员):
```powershell
Add-MpPreference -ExclusionPath "C:\Program Files\Adobe\Adobe After Effects 2025"
Add-MpPreference -ExclusionPath "C:\Users\Administrator\AppData\Roaming\Adobe\After Effects"
Add-MpPreference -ExclusionProcess "AfterFX.exe"
```

### 步骤 3: 验证 AEHeadless.exe 存在
```powershell
Test-Path "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AEHeadless.exe"
# 应返回 True
```

如果返回 False，说明 Defender 又删除了它，需要：
1. 检查 Defender 隔离区
2. 恢复文件并重新添加白名单

### 步骤 4: 运行配置恢复脚本
**以管理员身份运行**:
```
C:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae_backup\ae_backup_20260721_003925\restore_after_reinstall.bat
```

这会恢复:
- AE Process Manager
- MCP Bridge 文件
- Startup 监听器脚本
- 配置文件 (.mcp.json, .env)

### 步骤 5: 清除崩溃状态
```powershell
# 清除注册表崩溃标记
reg delete "HKCU\Software\Adobe\After Effects\25.3" /v AppState /f
reg delete "HKCU\Software\Adobe\After Effects\25.3" /v AppStateDunamisSessionID /f

# 删除崩溃状态文件
Remove-Item "$env:APPDATA\Adobe\After Effects\25.3\SCRPriorState.json" -ErrorAction SilentlyContinue
```

### 步骤 6: 启动 AE 并测试
```bash
# 启动 AE
python ae_process_manager.py

# 测试 MCP Bridge
python ae_mcp_client.py ping
```

---

## 📋 快速检查清单

重装后按顺序检查：

- [ ] AE 2025 安装完成
- [ ] Defender 白名单已添加 (3 项)
- [ ] AEHeadless.exe 存在
- [ ] 配置恢复脚本已运行
- [ ] 崩溃状态已清除
- [ ] AE 启动成功 (无 Crash Repair 弹窗)
- [ ] MCP Bridge 通信正常
- [ ] 手动安装需要的插件

---

## 🔧 故障排查命令

如果重装后仍崩溃，运行以下诊断：

```bash
# 完整诊断
py -3.11 c:\Users\Administrator\Desktop\AE-Knowledge-Vault\deep_diagnostic.py

# 检查 AE 状态
py -3.11 c:\Users\Administrator\Desktop\AE-Knowledge-Vault\check_state.py

# 查看 Plugin Loading 日志
type "$env:APPDATA\Adobe\After Effects\25.3\Plugin Loading.log" | findstr "could not be loaded"
```

---

## 📦 备份文件位置

**配置备份**: 
```
C:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae_backup\ae_backup_20260721_003925\
```

**包含**:
- `restore_after_reinstall.bat` - 自动恢复脚本
- `BACKUP_SUMMARY.txt` - 备份清单
- `scripts/` - 核心脚本
- `bridge/` - MCP Bridge 文件
- `startup/` - 干净的 Startup 脚本
- `config/` - 配置文件

---

## ⚠️ 重要提示

1. **Defender 白名单是关键** - 必须在启动 AE 前添加
2. **不要立即安装插件** - 先确认 AE 能稳定启动
3. **保留备份文件夹** - 直到确认 AE 完全正常
4. **命令行模式可用** - 即使 GUI 崩溃，仍可用 `-r` 和 `-s` 参数执行脚本

---

## 📞 如果问题仍然存在

如果按照以上流程操作后 AE 仍然崩溃：

1. 运行完整诊断脚本收集信息
2. 检查 Windows 事件日志中的 AE 错误
3. 考虑回滚最近的 Windows 更新
4. 联系 Adobe 支持并提供诊断报告

---

**生成工具**: `deep_diagnostic.py`, `fix_ae_root_cause.py`  
**备份工具**: `backup_ae_config.py`  
**恢复工具**: `restore_after_reinstall.bat`
