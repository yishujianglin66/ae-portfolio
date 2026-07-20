# 第六阶段：统一工作流与质量保证

> **目标**: 将四插件整合为标准化开发工作流，建立提交前自动检查，输出团队可复用的环境手册
> **关键指标**: 开发者 10 分钟进入编码状态，30 分钟完整搭建环境

---

## 6.1 10 分钟快速启动清单

### 每天打开 VSCode 后的标准流程

```
╔══════════════════════════════════════════════════════════════╗
║            AE StudioKit 开发环境 — 每日启动 SOP              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ⏱ 00:00  双击 VSCode 工作区文件                             ║
║           AE-Extension-Dev.code-workspace                    ║
║                                                              ║
║  ⏱ 00:30  VSCode 自动打开项目 + 终端就绪                      ║
║           ✅ 检查扩展侧边栏：4 个插件激活                      ║
║           ✅ 检查状态栏：无错误标记                            ║
║                                                              ║
║  ⏱ 01:00  启动 After Effects 2025                            ║
║           ✅ 确认 CEP 面板已打开 (窗口 → 扩展 → AE StudioKit) ║
║                                                              ║
║  ⏱ 02:00  验证 CEP 桥接                                      ║
║           ✅ 在 VSCode 终端执行：                              ║
║           curl -s http://127.0.0.1:8765/health               ║
║           → 应返回 {"status":"ok"}                            ║
║                                                              ║
║  ⏱ 03:00  快速测试连接                                       ║
║           ✅ 打开 test-bridge.html → 检查 evalScript 返回     ║
║           ✅ 或按 F5 运行 test-connection.jsx                  ║
║                                                              ║
║  ⏱ 05:00  选择今天的工作分支                                  ║
║           git checkout -b feature/xxx                        ║
║                                                              ║
║  ⏱ 07:00  打开目标文件，开始编码                              ║
║           ✅ Ctrl+Alt+R = 快速运行                            ║
║           ✅ F5 = 启动调试                                    ║
║           ✅ ae-layer-loop + Tab = 图层遍历模板                ║
║                                                              ║
║  ⏱ 10:00  🎯 进入高效编码状态                                 ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

### 每日环境健康检查命令

```bash
# 在 VSCode 终端执行 — 一键检查所有环境状态
echo "=== 开发环境健康检查 ==="

# 1. 检查 AE 是否运行
powershell "Get-Process 'AfterFX' -ErrorAction SilentlyContinue | Select-Object Id, ProcessName"

# 2. 检查 Python 服务器
curl -s --connect-timeout 3 http://127.0.0.1:8765/health 2>/dev/null || echo "⚠️  Python 服务器未运行"

# 3. 检查 CEP 扩展部署
ls "$APPDATA/Adobe/CEP/extensions/ae-vocal-remover/CSXS/manifest.xml" 2>/dev/null && echo "✅ CEP 扩展已部署" || echo "❌ CEP 扩展缺失"

# 4. 检查 BOM
for f in host/*.jsx host/**/*.jsx; do
    [ "$(xxd -l 3 -p "$f" 2>/dev/null)" = "efbbbf" ] || echo "⚠️  缺少 BOM: $f"
done

# 5. 检查废弃 API
grep -rn 'app\.refresh\|socket\|new Window' host/ --include="*.jsx" 2>/dev/null && echo "⚠️  发现潜在废弃API" || echo "✅ 无废弃API"

echo "=== 检查完成 ==="
```

## 6.2 提交前自动检查

### VSCode Tasks 配置

### 文件位置
```
.vscode/tasks.json
```

### 完整配置

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            // ═══════════════════════════════════════════
            // Task 1: 检查 UTF-8 BOM
            // ═══════════════════════════════════════════
            "label": "✅ 检查 UTF-8 BOM",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "missing=0; for f in $(find host/ -name '*.jsx' -type f); do if [ \"$(xxd -l 3 -p \"$f\")\" != \"efbbbf\" ]; then echo \"❌ 缺少BOM: $f\"; missing=$((missing+1)); fi; done; if [ $missing -eq 0 ]; then echo '✅ 所有 .jsx 文件均有 BOM'; else echo \"共 $missing 个文件缺少 BOM\"; exit 1; fi"
            ],
            "group": "test",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        },
        {
            // ═══════════════════════════════════════════
            // Task 2: 扫描 ES6+ 语法违规
            // ═══════════════════════════════════════════
            "label": "🔍 扫描 ES6 语法",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "echo '=== 扫描 ES6+ 语法违规 ==='; violations=0; echo '--- 检查 const ---'; grep -rn '\\bconst\\b' host/ --include='*.jsx' || echo '  ✅ 无'; echo '--- 检查 let ---'; grep -rn '\\blet\\b' host/ --include='*.jsx' || echo '  ✅ 无'; echo '--- 检查箭头函数 ---'; grep -rn '=>' host/ --include='*.jsx' || echo '  ✅ 无'; echo '--- 检查模板字符串 ---'; grep -rn '`' host/ --include='*.jsx' | grep -v '//' | grep -v '/\\*' || echo '  ✅ 无'; echo '--- 检查 class ---'; grep -rn '\\bclass\\b' host/ --include='*.jsx' || echo '  ✅ 无'; echo '=== 扫描完成 ==='"
            ],
            "group": "test",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        },
        {
            // ═══════════════════════════════════════════
            // Task 3: 扫描废弃 API
            // ═══════════════════════════════════════════
            "label": "⚠️ 扫描废弃 API",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "echo '=== 扫描废弃/危险 API ==='; echo '--- app.refresh (已废弃) ---'; grep -rn 'app\\.refresh' host/ --include='*.jsx' && echo '  🔴 发现!' || echo '  ✅ 无'; echo '--- Socket (安全风险) ---'; grep -rn '\\bSocket\\b' host/ --include='*.jsx' | grep -v '//' && echo '  🔴 发现!' || echo '  ✅ 无'; echo '--- confirm() (CEP不可用) ---'; grep -rn '\\bconfirm(' host/ --include='*.jsx' | grep -v '//' && echo '  🟡 注意' || echo '  ✅ 无'; echo '--- system.callSystem (需审查) ---'; count=$(grep -rn 'system\\.callSystem' host/ --include='*.jsx' | wc -l); echo \"  ℹ️  共 $count 处 (检查是否异步)\"; echo '=== 扫描完成 ==='"
            ],
            "group": "test",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        },
        {
            // ═══════════════════════════════════════════
            // Task 4: 全量提交前检查 (运行上述所有)
            // ═══════════════════════════════════════════
            "label": "🚀 全量提交前检查",
            "dependsOrder": "sequence",
            "dependsOn": [
                "✅ 检查 UTF-8 BOM",
                "🔍 扫描 ES6 语法",
                "⚠️ 扫描废弃 API"
            ],
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "problemMatcher": []
        },
        {
            // ═══════════════════════════════════════════
            // Task 5: 自动添加 BOM
            // ═══════════════════════════════════════════
            "label": "🔧 自动添加 BOM",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "fixed=0; for f in $(find host/ -name '*.jsx' -type f); do if [ \"$(xxd -l 3 -p \"$f\")\" != \"efbbbf\" ]; then printf '\\xef\\xbb\\xbf' | cat - \"$f\" > \"$f.tmp\" && mv \"$f.tmp\" \"$f\" && echo \"✅ 已添加BOM: $f\"; fixed=$((fixed+1)); fi; done; echo \"共修复 $fixed 个文件\""
            ],
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        },
        {
            // ═══════════════════════════════════════════
            // Task 6: 部署到 CEP 扩展目录
            // ═══════════════════════════════════════════
            "label": "📦 部署到 CEP",
            "type": "shell",
            "command": "bash",
            "args": [
                "-c",
                "cep_dir=\"$APPDATA/Adobe/CEP/extensions/ae-vocal-remover\"; echo \"部署到: $cep_dir\"; cp -r host/*.jsx \"$cep_dir/host/\" 2>/dev/null; cp -r host/*/ \"$cep_dir/host/\" 2>/dev/null; cp client/CSInterface.js \"$cep_dir/client/\" 2>/dev/null; cp CSXS/manifest.xml \"$cep_dir/CSXS/\" 2>/dev/null; echo '✅ 部署完成 — 重启 AE 生效'"
            ],
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        }
    ]
}
```

### 提交前检查流程

```
git commit 前:
    │
    ├─ Ctrl+Shift+B → 运行默认构建任务 "🚀 全量提交前检查"
    │   ├─ ✅ UTF-8 BOM 检查
    │   ├─ 🔍 ES6 语法扫描
    │   └─ ⚠️ 废弃 API 扫描
    │
    ├─ 所有通过? → git commit
    │
    └─ 有问题? → 🔧 自动添加 BOM → 修复 → 重新检查 → git commit
```

## 6.3 VSCode 工作区文件

### 文件位置
```
skills/AE-Extension-Dev.code-workspace
```

### 完整配置

```json
{
    "folders": [
        {
            "name": "AE Vocal Remover (主项目)",
            "path": "ae-vocal-remover"
        },
        {
            "name": "Skills (项目管理)",
            "path": "."
        }
    ],
    "settings": {
        // ═══ 编辑器基础 ═══
        "editor.tabSize": 4,
        "editor.insertSpaces": true,
        "editor.detectIndentation": false,
        "editor.renderWhitespace": "boundary",
        "editor.rulers": [100, 120],
        "editor.bracketPairColorization.enabled": true,
        "editor.guides.bracketPairs": "active",

        // ═══ 自动保存 ═══
        "files.autoSave": "onFocusChange",
        "files.autoSaveDelay": 500,

        // ═══ 编码 ═══
        "files.encoding": "utf8",
        "files.autoGuessEncoding": false,
        "[javascript]": {
            "files.encoding": "utf8"
        },

        // ═══ 排除干扰文件 ═══
        "files.exclude": {
            "**/node_modules": true,
            "**/__pycache__": true,
            "**/*.pyc": true,
            "**/.git": true,
            "**/output": true,
            "**/temp": true,
            "**/ffmpeg-*": true
        },
        "files.watcherExclude": {
            "**/output/**": true,
            "**/temp/**": true,
            "**/ffmpeg-*/**": true
        },

        // ═══ ExtendScript Debugger ═══
        "extendscript.debug.breakOnCaughtExceptions": false,
        "extendscript.debug.breakOnUncaughtExceptions": true,
        "extendscript.debug.showExceptionStack": true,

        // ═══ AE JSX Runner ═══
        "aeRunner.aePath": "C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\AfterFX.exe",
        "aeRunner.targetApp": "aftereffects",
        "aeRunner.port": 8089,
        "aeRunner.saveBeforeRun": true,
        "aeRunner.encoding": "utf8",

        // ═══ JS JSX Snippets ═══
        "editor.snippetSuggestions": "top",
        "editor.tabCompletion": "on",

        // ═══ 终端 ═══
        "terminal.integrated.defaultProfile.windows": "Git Bash",
        "terminal.integrated.cwd": "${workspaceFolder:AE Vocal Remover (主项目)}",

        // ═══ 推荐插件 ═══
        "extensions.ignoreRecommendations": false
    },
    "extensions": {
        "recommendations": [
            "adobe.extendscript-debug",
            "voidgazer.ae-jsx-runner",
            "adpyke.js-jsx-snippets",
            "alibaba-cloud.tongyi-lingma",
            "dbaeumer.vscode-eslint",
            "editorconfig.editorconfig"
        ]
    },
    "launch": {
        "version": "0.2.0",
        "configurations": [],
        "compounds": []
    }
}
```

## 6.4 工作区设置文件

### `.vscode/settings.json` (主项目)

```json
{
    // ═══════════════════════════════════════════════════
    // AE StudioKit — VSCode 工作区设置
    // ═══════════════════════════════════════════════════

    // ── 编码 ──
    "files.encoding": "utf8",
    "files.autoGuessEncoding": false,

    // ── 排除 (减少文件监视器开销) ──
    "files.exclude": {
        "**/output": true,
        "**/temp": true,
        "**/ffmpeg-*": true,
        "**/__pycache__": true
    },
    "files.watcherExclude": {
        "**/output/**": true,
        "**/temp/**": true,
        "**/ffmpeg-*/**": true,
        "**/node_modules/**": true
    },
    "search.exclude": {
        "**/output": true,
        "**/temp": true,
        "**/ffmpeg-*": true
    },

    // ── ExtendScript Debugger ──
    "extendscript.debug.breakOnCaughtExceptions": false,
    "extendscript.debug.breakOnUncaughtExceptions": true,
    "extendscript.debug.showExceptionStack": true,

    // ── AE JSX Runner ──
    "aeRunner.aePath": "C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\AfterFX.exe",
    "aeRunner.targetApp": "aftereffects",
    "aeRunner.port": 8089,
    "aeRunner.saveBeforeRun": true,
    "aeRunner.encoding": "utf8",

    // ── Snippets ──
    "editor.snippetSuggestions": "top",
    "editor.tabCompletion": "on",

    // ── 编辑器 ──
    "editor.tabSize": 4,
    "editor.insertSpaces": true,
    "editor.rulers": [100, 120],

    // ── 语言特定 ──
    "[javascript]": {
        "editor.tabSize": 4,
        "editor.insertSpaces": true,
        "files.encoding": "utf8"
    },
    "[json]": {
        "editor.tabSize": 2
    },
    "[jsonc]": {
        "editor.tabSize": 2
    }
}
```

---

> **最终产出**: [开发环境标准化手册](./AE_DEV_ENVIRONMENT_MANUAL.md)
