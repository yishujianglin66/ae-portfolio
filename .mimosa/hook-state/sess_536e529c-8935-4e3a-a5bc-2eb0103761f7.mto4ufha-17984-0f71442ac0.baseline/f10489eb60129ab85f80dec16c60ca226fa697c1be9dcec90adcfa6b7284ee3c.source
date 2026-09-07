"""
integrations/remotion_agent_adapter.py — Remotion Agent Skills 适配器
=====================================================================

Remotion Agent Skills: AI Agent 驱动的视频生成
  - 2026-01 Remotion 官方推出 Agent Skills
  - 52k+ stars，React 编程式视频生成
  - 通过 AI Agent 生成 Remotion 组件代码 → 渲染视频
  - GitHub: https://github.com/remotion-dev/remotion

集成点:
  - MG 动画管线: StyleSpec → Remotion 组件 → 渲染
  - 数据驱动动画: JSON 数据 → 图表/文字动画 → MP4
  - 与 Motion Canvas 互补: Remotion 适合 Web/数据动画，Motion Canvas 适合 2D 矢量

用法:
    from integrations.remotion_agent_adapter import RemotionAgentAdapter
    adapter = RemotionAgentAdapter()
    result = adapter.execute("generate_mg_animation", {
        "spec": {"type": "data_chart", "data": [...], "style": "corporate"},
        "output_path": "output/chart_animation.mp4",
    })
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_EXTERNAL_DIR = _PROJECT_ROOT / "external"
# Remotion 已通过 OpenMontage 的 remotion-composer 子目录存在
_OPENMONTAGE_REMOTION = _EXTERNAL_DIR / "OpenMontage" / "remotion-composer"
# 独立 Remotion 项目目录
_REMOTION_DIR = _EXTERNAL_DIR / "remotion"


class RemotionAgentAdapter:
    """Remotion Agent Skills 适配器

    封装 Remotion 视频生成管线，提供:
    1. generate_mg_animation: 规格 → Remotion 组件 → 渲染
    2. render_component: 已有组件 → 渲染
    3. list_templates: 可用 MG 动画模板
    4. check_environment: Node.js + Remotion 环境检查
    """

    TOOL_NAME = "remotion_agent"
    SUPPORTED_OPERATIONS = [
        "generate_mg_animation",
        "render_component",
        "list_templates",
        "check_environment",
        "get_model_info",
        "create_project",
    ]

    # MG 动画模板类型
    TEMPLATE_TYPES = [
        "data_chart",          # 数据图表动画
        "typography",          # 排版动画
        "logo_reveal",         # Logo 展示
        "infographic",         # 信息图
        "lower_third",         # 下方三分之一字幕条
        "transition_wipe",     # 转场擦除
        "countdown",           # 倒计时
        "social_media_card",   # 社交媒体卡片
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._remotion_available = _REMOTION_DIR.is_dir()
        self._openmontage_remotion = _OPENMONTAGE_REMOTION.is_dir()
        self._simulate = not (self._remotion_available or self._openmontage_remotion)
        self._env_check = self._check_environment()

    def _check_environment(self) -> Dict[str, Any]:
        checks: Dict[str, Any] = {
            "remotion_project": self._remotion_available,
            "openmontage_remotion": self._openmontage_remotion,
            "simulate_mode": self._simulate,
        }

        # Node.js
        try:
            r = subprocess.run(
                ["node", "--version"], capture_output=True, text=True, timeout=5
            )
            checks["node_version"] = r.stdout.strip() if r.returncode == 0 else None
            checks["node_ok"] = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["node_version"] = None
            checks["node_ok"] = False

        # npm
        try:
            r = subprocess.run(
                ["npm", "--version"], capture_output=True, text=True, timeout=5
            )
            checks["npm_version"] = r.stdout.strip() if r.returncode == 0 else None
            checks["npm_ok"] = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["npm_version"] = None
            checks["npm_ok"] = False

        # Remotion CLI
        try:
            r = subprocess.run(
                ["npx", "remotion", "--version"],
                capture_output=True, text=True, timeout=15,
            )
            checks["remotion_cli"] = r.stdout.strip() if r.returncode == 0 else None
            checks["remotion_cli_ok"] = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            checks["remotion_cli"] = None
            checks["remotion_cli_ok"] = False

        # 检查 node_modules
        for d in [_REMOTION_DIR / "node_modules", _OPENMONTAGE_REMOTION / "node_modules"]:
            if d.is_dir():
                checks["remotion_deps_installed"] = True
                break
        else:
            checks["remotion_deps_installed"] = False

        return checks

    def check_available(self) -> bool:
        return (
            self._env_check.get("node_ok", False)
            and (self._remotion_available or self._openmontage_remotion)
        )

    def list_operations(self) -> List[str]:
        return self.SUPPORTED_OPERATIONS

    def execute(self, operation: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}

        handlers = {
            "check_environment": lambda: self._env_check,
            "list_templates": self._list_templates,
            "get_model_info": self._get_model_info,
            "generate_mg_animation": lambda: self._generate_mg_animation(params),
            "render_component": lambda: self._render_component(params),
            "create_project": lambda: self._create_project(params),
        }

        handler = handlers.get(operation)
        if handler:
            return handler()
        return {"status": "error", "message": f"Unknown operation: {operation}"}

    def _list_templates(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "templates": [
                {"id": t, "description": f"MG animation: {t.replace('_', ' ').title()}"}
                for t in self.TEMPLATE_TYPES
            ],
        }

    def _get_model_info(self) -> Dict[str, Any]:
        return {
            "status": "success",
            "name": "Remotion Agent Skills",
            "version": "4.x (2026-01)",
            "github": "https://github.com/remotion-dev/remotion",
            "stars": "52k+",
            "license": "BSL-1.0 (Business Source License)",
            "key_features": [
                "React 编程式视频生成",
                "Agent Skills: AI 生成组件代码 → 自动渲染",
                "丰富的动画原语 (spring, interpolate, Sequence)",
                "跨平台输出: MP4/WebM/GIF",
                "数据驱动: JSON props → 动态图表/文字",
            ],
            "agent_skills": {
                "description": "AI Agent 通过自然语言描述生成 Remotion 组件",
                "input": "自然语言视频规格 + 数据",
                "output": "React 组件代码 + 渲染后视频",
            },
        }

    def _generate_mg_animation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """生成 MG 动画

        Args:
            params: {
                "spec": dict,           # 动画规格 {type, data, style, duration}
                "output_path": str,     # 输出路径
                "fps": int,             # 帧率
                "width": int,           # 宽度
                "height": int,          # 高度
            }
        """
        spec = params.get("spec", {})
        output_path = params.get("output_path", "")
        anim_type = spec.get("type", "typography")

        if self._simulate:
            # 模拟模式: 生成 Remotion 组件代码模板
            component_code = self._generate_component_template(spec)
            return {
                "status": "success",
                "mode": "simulate",
                "message": "Remotion 项目未初始化，使用模拟模式",
                "component_code": component_code,
                "output_path": output_path or f"output_remotion_{anim_type}.mp4",
                "simulated_output": True,
            }

        # 实际执行: 生成组件 → 渲染
        try:
            project_dir = _REMOTION_DIR if self._remotion_available else _OPENMONTAGE_REMOTION

            # 1. 生成组件代码
            component_code = self._generate_component_template(spec)
            component_path = project_dir / "src" / "GeneratedAnimation.tsx"
            component_path.parent.mkdir(parents=True, exist_ok=True)
            component_path.write_text(component_code, encoding="utf-8")

            # 2. 渲染
            cmd = [
                "npx", "remotion", "render",
                "src/index.ts",
                "GeneratedAnimation",
                output_path or f"output_remotion_{anim_type}.mp4",
            ]

            if params.get("fps"):
                cmd.extend(["--fps", str(params["fps"])])
            if params.get("width"):
                cmd.extend(["--width", str(params["width"])])
            if params.get("height"):
                cmd.extend(["--height", str(params["height"])])

            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=300, cwd=str(project_dir),
            )

            if proc.returncode == 0:
                return {
                    "status": "success",
                    "mode": "real",
                    "output_path": output_path or f"output_remotion_{anim_type}.mp4",
                }
            else:
                return {
                    "status": "error",
                    "stderr": proc.stderr[-500:] if proc.stderr else "",
                }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _render_component(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """渲染已有组件"""
        return self._generate_mg_animation(params)

    def _create_project(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """创建 Remotion 项目"""
        project_name = params.get("project_name", "mg-animation")
        target_dir = _EXTERNAL_DIR / "remotion"

        if self._simulate:
            return {
                "status": "success",
                "mode": "simulate",
                "message": f"将创建 Remotion 项目: {project_name}",
                "target_dir": str(target_dir),
            }

        try:
            cmd = [
                "npx", "create-video", project_name,
                "--yes",  # 非交互
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=120, cwd=str(_EXTERNAL_DIR),
            )
            if proc.returncode == 0:
                return {
                    "status": "success",
                    "project_dir": str(target_dir),
                    "message": "Remotion 项目创建成功",
                }
            else:
                return {"status": "error", "stderr": proc.stderr[-500:]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _generate_component_template(self, spec: Dict[str, Any]) -> str:
        """生成 Remotion 组件代码模板"""
        anim_type = spec.get("type", "typography")
        data = spec.get("data", [])
        style = spec.get("style", "corporate")
        duration_sec = spec.get("duration", 5)

        templates = {
            "data_chart": self._template_data_chart(data, style, duration_sec),
            "typography": self._template_typography(spec.get("text", "Hello World"), style, duration_sec),
            "logo_reveal": self._template_logo_reveal(style, duration_sec),
        }

        return templates.get(anim_type, templates["typography"])

    def _template_data_chart(self, data: list, style: str, duration: int) -> str:
        return f'''import {{ AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate }} from "remotion";

export const GeneratedAnimation: React.FC<{{}}> = () => {{
  const frame = useCurrentFrame();
  const {{ fps, durationInFrames }} = useVideoConfig();
  const progress = spring({{ frame, fps, config: {{ damping: 80 }} }});

  const data = {json.dumps(data or [10, 25, 40, 60, 80, 55, 35])};
  const maxVal = Math.max(...data);
  const barWidth = 60;
  const gap = 20;

  return (
    <AbsoluteFill style={{{{ backgroundColor: "{self._style_bg(style)}", display: "flex", alignItems: "flex-end", padding: 60 }}}}>
      {{data.map((val, i) => {{
        const barHeight = interpolate(progress, [0, 1], [0, (val / maxVal) * 500]]);
        const delay = spring({{ frame: frame - i * 5, fps, config: {{ damping: 80 }} }});
        return (
          <div key={{i}} style={{{{ 
            width: barWidth, marginLeft: gap,
            height: Math.max(0, delay * (val / maxVal) * 500),
            backgroundColor: "{self._style_accent(style)}",
            borderRadius: 8,
          }}}} />
        );
      }})}}
    </AbsoluteFill>
  );
}};
'''

    def _template_typography(self, text: str, style: str, duration: int) -> str:
        return f'''import {{ AbsoluteFill, spring, useCurrentFrame, useVideoConfig }} from "remotion";

export const GeneratedAnimation: React.FC<{{}}> = () => {{
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();
  const scale = spring({{ frame, fps, config: {{ damping: 12, mass: 0.5 }} }});
  const opacity = Math.min(1, frame / 15);

  return (
    <AbsoluteFill style={{{{ backgroundColor: "{self._style_bg(style)}", justifyContent: "center", alignItems: "center" }}}}>
      <h1 style={{{{
        fontSize: 80, fontWeight: 900,
        color: "{self._style_accent(style)}",
        transform: `scale(${{scale}})`,
        opacity,
        fontFamily: "Inter, sans-serif",
      }}}}>
        {text}
      </h1>
    </AbsoluteFill>
  );
}};
'''

    def _template_logo_reveal(self, style: str, duration: int) -> str:
        return f'''import {{ AbsoluteFill, spring, useCurrentFrame, useVideoConfig, interpolate }} from "remotion";

export const GeneratedAnimation: React.FC<{{}}> = () => {{
  const frame = useCurrentFrame();
  const {{ fps }} = useVideoConfig();
  const scale = spring({{ frame, fps, config: {{ damping: 15, mass: 1 }} }});
  const lineWidth = interpolate(frame, [0, 30], [0, 300], {{ extrapolateRight: "clamp" }});

  return (
    <AbsoluteFill style={{{{ backgroundColor: "{self._style_bg(style)}", justifyContent: "center", alignItems: "center" }}}}>
      <div style={{{{ textAlign: "center" }}}}>
        <div style={{{{
          width: lineWidth, height: 4,
          backgroundColor: "{self._style_accent(style)}",
          margin: "0 auto 20px",
        }}}} />
        <h1 style={{{{
          fontSize: 60, fontWeight: 700,
          color: "{self._style_accent(style)}",
          transform: `scale(${{scale}})`,
          opacity: Math.min(1, frame / 20),
        }}}}>
          LOGO
        </h1>
      </div>
    </AbsoluteFill>
  );
}};
'''

    @staticmethod
    def _style_bg(style: str) -> str:
        styles = {
            "corporate": "#1a1a2e",
            "playful": "#fff3e0",
            "minimal": "#ffffff",
            "dark": "#0d0d0d",
            "gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
        }
        return styles.get(style, "#1a1a2e")

    @staticmethod
    def _style_accent(style: str) -> str:
        styles = {
            "corporate": "#4fc3f7",
            "playful": "#ff6d00",
            "minimal": "#333333",
            "dark": "#00e5ff",
            "gradient": "#ffffff",
        }
        return styles.get(style, "#4fc3f7")


def get_adapter(config: Optional[Dict[str, Any]] = None) -> RemotionAgentAdapter:
    return RemotionAgentAdapter(config)
