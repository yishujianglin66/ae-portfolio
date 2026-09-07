"""
integrations/motion_canvas_adapter.py — Motion Canvas 代码动画适配器
=====================================================================

手书/MG 动画集成方案 P1-6: Motion Canvas (motion-canvas/motion-canvas)

TypeScript 声明式动画引擎，与 Remotion (React) 双轨互补:
  - Motion Canvas: 纯 TS + Canvas 2D, 更轻量, 生成器函数控制时间线
  - Remotion: React 组件式, 生态更大 (52k★)
  - MGTemplateEngine 可按后端选择: pillow_ffmpeg / remotion / motion_canvas

操作:
  1. init_project: 在 external/motion_canvas 生成最小可运行项目脚手架
  2. generate_scene: 由 MG 动画规格生成 TSX 场景文件
  3. render: 调用 `npm run build` 渲染 MP4 (需 Node.js + 依赖)
  4. check_environment: 环境检查 (node/npm/依赖)

用法:
    from integrations.motion_canvas_adapter import MotionCanvasAdapter
    adapter = MotionCanvasAdapter()
    adapter.execute("init_project", {})
    adapter.execute("generate_scene", {
        "spec": {"type": "typography", "title": "Hello", "duration": 2.0},
        "scene_name": "title_scene",
    })
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MC_PROJECT_DIR = _PROJECT_ROOT / "external" / "motion_canvas"


class MotionCanvasAdapter:
    """Motion Canvas TypeScript 代码动画适配器

    提供:
    1. init_project: 生成离线可构建的最小项目脚手架 (无需网络)
    2. generate_scene: MGAnimationSpec → TSX 场景文件
    3. render: npm run build → output/ 下 MP4
    4. check_environment: node/npm/项目就绪检查
    """

    TOOL_NAME = "motion_canvas"
    SUPPORTED_OPERATIONS = [
        "init_project",
        "generate_scene",
        "render",
        "check_environment",
        "list_templates",
    ]

    # MC 核心依赖 (init_project 写入 package.json, 由用户离线安装)
    CORE_DEPS = {
        "@motion-canvas/core": "^3.17.0",
        "@motion-canvas/2d": "^3.17.0",
        "@motion-canvas/vite-plugin": "^3.17.0",
        "@motion-canvas/ui": "^3.17.0",
        "vite": "^5.4.0",
        "typescript": "^5.5.0",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.project_dir = Path(self.config.get("project_dir", _MC_PROJECT_DIR))
        self._node_ok = shutil.which("node") is not None
        self._npm_ok = shutil.which("npm") is not None or shutil.which("npm.cmd") is not None

    def check_available(self) -> bool:
        """完全可用 = node 存在 + 项目已初始化且依赖已安装"""
        return (
            self._node_ok
            and (self.project_dir / "node_modules").is_dir()
        )

    # ------------------------------------------------------------------
    #  操作: init_project
    # ------------------------------------------------------------------
    def _init_project(self) -> Dict[str, Any]:
        d = self.project_dir
        d.mkdir(parents=True, exist_ok=True)
        (d / "src").mkdir(exist_ok=True)

        package_json = {
            "name": "ae-motion-canvas",
            "private": True,
            "version": "1.0.0",
            "description": "AE-Knowledge-Vault MG 动画 Motion Canvas 项目 (P1-6)",
            "scripts": {
                "serve": "vite",
                "build": "tsc && vite build",
                "render": "vite build --mode render",
            },
            "dependencies": {
                "@motion-canvas/core": self.CORE_DEPS["@motion-canvas/core"],
                "@motion-canvas/2d": self.CORE_DEPS["@motion-canvas/2d"],
            },
            "devDependencies": {
                "@motion-canvas/vite-plugin": self.CORE_DEPS["@motion-canvas/vite-plugin"],
                "@motion-canvas/ui": self.CORE_DEPS["@motion-canvas/ui"],
                "vite": self.CORE_DEPS["vite"],
                "typescript": self.CORE_DEPS["typescript"],
            },
        }
        (d / "package.json").write_text(
            json.dumps(package_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        tsconfig = {
            "compilerOptions": {
                "target": "ESNext",
                "module": "ESNext",
                "moduleResolution": "bundler",
                "jsx": "react-jsx",
                "jsxImportSource": "@motion-canvas/2d/lib",
                "strict": True,
                "skipLibCheck": True,
                "noEmit": True,
            },
            "include": ["src"],
        }
        (d / "tsconfig.json").write_text(
            json.dumps(tsconfig, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        vite_config = (
            "import {defineConfig} from 'vite';\n"
            "import motionCanvas from '@motion-canvas/vite-plugin';\n\n"
            "export default defineConfig({\n"
            "  plugins: [motionCanvas()],\n"
            "});\n"
        )
        (d / "vite.config.ts").write_text(vite_config, encoding="utf-8")

        # 项目入口
        project_ts = (
            "import {makeProject} from '@motion-canvas/core';\n"
            "import example from './scenes/example?scene';\n\n"
            "export default makeProject({\n"
            "  scenes: [example],\n"
            "});\n"
        )
        (d / "src" / "project.ts").write_text(project_ts, encoding="utf-8")

        # ?scene 后缀模块类型声明 (tsc 必需)
        scene_dts = (
            "declare module '*?scene' {\n"
            "  import type {FullSceneDescription} from '@motion-canvas/core/lib/scenes';\n"
            "  const value: FullSceneDescription;\n"
            "  export default value;\n"
            "}\n"
        )
        (d / "src" / "scene.d.ts").write_text(scene_dts, encoding="utf-8")

        # 示例场景
        example = self._scene_typography(
            {"title": "Motion Canvas Ready", "duration": 2.0}
        )
        (d / "src" / "scenes").mkdir(exist_ok=True)
        (d / "src" / "scenes" / "example.tsx").write_text(example, encoding="utf-8")

        return {
            "status": "success",
            "project_dir": str(d),
            "files": ["package.json", "tsconfig.json", "vite.config.ts",
                      "src/project.ts", "src/scene.d.ts", "src/scenes/example.tsx"],
            "next_step": "npm install (需网络或离线缓存), 然后 npm run build",
        }

    # ------------------------------------------------------------------
    #  操作: generate_scene
    # ------------------------------------------------------------------
    def _scene_typography(self, spec: Dict[str, Any]) -> str:
        title = spec.get("title", "Motion Canvas")
        duration = spec.get("duration", 2.0)
        accent = spec.get("style", {}).get("accent", "#4fc3f7")
        return f'''import {{makeScene2D}} from '@motion-canvas/2d/lib/scenes';
import {{Txt}} from '@motion-canvas/2d/lib/components';
import {{all, sequence}} from '@motion-canvas/core/lib/flow';
import {{createRef}} from '@motion-canvas/core/lib/utils';

export default makeScene2D(function* (view) {{
  view.fill('#1a1a2e');
  const title = createRef<Txt>();
  view.add(
    <Txt
      ref={{title}}
      text="{title}"
      fontSize={{80}}
      fill="{accent}"
      opacity={{0}}
    />,
  );
  yield* all(
    title().opacity(1, {duration / 2}),
    title().scale(1.1, {duration}).to(1, {duration / 2}),
  );
}});
'''

    def _scene_data_chart(self, spec: Dict[str, Any]) -> str:
        data = spec.get("data", [{"label": "A", "value": 50}])
        accent = spec.get("style", {}).get("accent", "#4fc3f7")
        duration = spec.get("duration", 3.0)
        max_v = max((d.get("value", 0) for d in data), default=1) or 1
        n = len(data)

        refs = "\n".join(
            "  const bar%d = createRef<Rect>();" % i for i in range(n)
        )
        bars = "\n".join(
            '      <Rect ref={bar%d} x={%d} y={200} size={[80, 0]} '
            'fill="%s" radius={8} offset={[0, 1]} />'
            % (i, -200 + i * 120, accent)
            for i in range(n)
        )
        anims = "\n".join(
            "      bar%d().size([80, %d], %.3f, easeOutCubic),"
            % (i, int(400 * d.get("value", 0) / max_v), duration / n)
            for i, d in enumerate(data)
        )
        return (
            "import {makeScene2D} from '@motion-canvas/2d/lib/scenes';\n"
            "import {Rect} from '@motion-canvas/2d/lib/components';\n"
            "import {sequence} from '@motion-canvas/core/lib/flow';\n"
            "import {createRef} from '@motion-canvas/core/lib/utils';\n"
            "import {easeOutCubic} from '@motion-canvas/core/lib/tweening';\n"
            "\n"
            "export default makeScene2D(function* (view) {\n"
            "  view.fill('#1a1a2e');\n"
            + refs + "\n"
            "  view.add(\n"
            "    <>\n"
            + bars + "\n"
            "    </>,\n"
            "  );\n"
            "  yield* sequence(\n"
            "    %.3f,\n" % (duration / n / 2)
            + anims + "\n"
            "  );\n"
            "});\n"
        )

    def _scene_shape(self, spec: Dict[str, Any]) -> str:
        accent = spec.get("style", {}).get("accent", "#4fc3f7")
        secondary = spec.get("style", {}).get("secondary", "#e040fb")
        duration = spec.get("duration", 2.0)
        return f'''import {{makeScene2D}} from '@motion-canvas/2d/lib/scenes';
import {{Circle, Rect}} from '@motion-canvas/2d/lib/components';
import {{all}} from '@motion-canvas/core/lib/flow';
import {{createRef}} from '@motion-canvas/core/lib/utils';

export default makeScene2D(function* (view) {{
  view.fill('#1a1a2e');
  const circle = createRef<Circle>();
  const rect = createRef<Rect>();
  view.add(
    <>
      <Circle ref={{circle}} size={{0}} fill="{accent}" x={{-150}} />
      <Rect ref={{rect}} size={{0}} fill="{secondary}" x={{150}} radius={12} />
    </>,
  );
  yield* all(
    circle().size(200, {duration / 2}),
    rect().size(160, {duration / 2}),
    circle().rotation(360, {duration}),
  );
}});
'''

    def _generate_scene(self, params: Dict[str, Any]) -> Dict[str, Any]:
        spec = params.get("spec", {})
        scene_name = params.get("scene_name", "generated_scene")
        stype = spec.get("type", "typography")

        generators = {
            "typography": self._scene_typography,
            "data_chart": self._scene_data_chart,
            "shape": self._scene_shape,
            "transition": self._scene_shape,
            "infographic": self._scene_data_chart,
        }
        gen = generators.get(stype)
        if gen is None:
            return {"status": "error", "error": f"不支持的动画类型: {stype}"}

        scenes_dir = self.project_dir / "src" / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        out = scenes_dir / f"{scene_name}.tsx"
        out.write_text(gen(spec), encoding="utf-8")
        return {
            "status": "success",
            "scene_path": str(out),
            "type": stype,
            "scene_name": scene_name,
        }

    # ------------------------------------------------------------------
    #  操作: render
    # ------------------------------------------------------------------
    def _render(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self._node_ok or not self._npm_ok:
            return {
                "status": "error",
                "simulate": True,
                "error": "Node.js/npm 不可用, 无法真实渲染 (脚手架与场景已生成)",
            }
        if not (self.project_dir / "node_modules").is_dir():
            return {
                "status": "error",
                "simulate": True,
                "error": "依赖未安装 (node_modules 不存在), 请先 npm install",
            }
        timeout = params.get("timeout", 600)
        try:
            # Windows 下 npm 需要 shell=True; 强制 utf-8 避免 GBK 解码失败 (vite 输出含 ANSI/特殊字符)
            r = subprocess.run(
                "npm run build", shell=True, cwd=str(self.project_dir),
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                return {"status": "error", "error": (r.stderr or "")[-2000:]}
            return {
                "status": "success",
                "simulate": False,
                "output_dir": str(self.project_dir / "dist"),
                "log_tail": (r.stdout or "")[-1000:],
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"渲染超时 ({timeout}s)"}

    # ------------------------------------------------------------------
    #  执行入口
    # ------------------------------------------------------------------
    def execute(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if operation not in self.SUPPORTED_OPERATIONS:
            return {"status": "error", "error": f"不支持的操作: {operation}"}
        if operation == "init_project":
            return self._init_project()
        if operation == "generate_scene":
            return self._generate_scene(params)
        if operation == "render":
            return self._render(params)
        if operation == "check_environment":
            return {
                "status": "success",
                "node_available": self._node_ok,
                "npm_available": self._npm_ok,
                "project_dir": str(self.project_dir),
                "project_initialized": (self.project_dir / "package.json").is_file(),
                "deps_installed": (self.project_dir / "node_modules").is_dir(),
                "fully_available": self.check_available(),
            }
        if operation == "list_templates":
            return {
                "status": "success",
                "templates": ["typography", "data_chart", "shape",
                              "transition", "infographic"],
            }
        return {"status": "error", "error": "未实现的操作"}
