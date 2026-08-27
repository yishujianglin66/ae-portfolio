#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nexrender 集成模块 - 将 nexrender 的模板化渲染能力融入 AE 自动化工作流

nexrender 是一个数据驱动的 AE 渲染自动化工具，支持：
- 模板化视频生成（JSON 配置驱动）
- 批量渲染
- 动态数据填充
- 插件系统扩展

参考: https://github.com/inlife/nexrender
"""

import json
import os
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger


class NexrenderIntegration:
    """nexrender 集成器"""

    def __init__(
        self,
        node_path: Optional[str] = None,
        nexrender_path: Optional[str] = None,
        ae_path: Optional[str] = None,
    ):
        self.node_path = node_path or self._find_node()
        self.nexrender_path = nexrender_path or self._find_nexrender()
        self.ae_path = ae_path
        self._ensure_dependencies()

    def _find_node(self) -> str:
        """查找 Node.js 路径"""
        candidates = [
            "node",
            "node.exe",
            os.environ.get("NODE_PATH"),
            os.path.join(os.environ.get("ProgramFiles", ""), "nodejs", "node.exe"),
            os.path.join(os.environ.get("ProgramFiles(x86)", ""), "nodejs", "node.exe"),
        ]
        for candidate in candidates:
            if candidate and self._is_executable(candidate):
                return candidate
        return "node"

    def _find_nexrender(self) -> str:
        """查找 nexrender 路径"""
        # 优先查找全局安装的 nexrender-cli
        try:
            result = subprocess.run(
                ["npm", "list", "-g", "nexrender-cli"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "nexrender-cli" in result.stdout:
                return "npx nexrender"
        except Exception:
            pass

        # 查找本地安装
        local_nexrender = Path(__file__).parent.parent / "node_modules" / ".bin" / "nexrender"
        if local_nexrender.exists():
            return str(local_nexrender)

        return "npx nexrender"

    def _is_executable(self, path: str) -> bool:
        """检查路径是否为可执行文件"""
        try:
            subprocess.run(
                [path, "--version"],
                capture_output=True,
                timeout=5,
            )
            return True
        except Exception:
            return False

    def _ensure_dependencies(self):
        """确保依赖已安装"""
        if self._is_executable(self.node_path):
            logger.info(f"Node.js found: {self.node_path}")
        else:
            logger.warning("Node.js not found, nexrender features may be limited")

    async def is_available(self) -> bool:
        """检查 nexrender 是否可用"""
        if not self._is_executable(self.node_path):
            return False

        try:
            proc = await asyncio.create_subprocess_shell(
                f"{self.node_path} -e \"try {{\n  const nexrender = await import('nexrender');\n  console.log('nexrender available');\n}} catch(e) {{\n  console.log('nexrender not installed');\n}}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                timeout=15,
            )
            stdout, _ = await proc.communicate()
            return "nexrender available" in stdout.decode()
        except Exception:
            return False

    def create_template_config(
        self,
        template_path: str,
        output_path: str,
        data: Dict[str, Any],
        render_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """创建 nexrender 模板配置

        Args:
            template_path: AE 模板项目文件路径 (.aep)
            output_path: 输出视频路径
            data: 动态数据（用于填充模板中的占位符）
            render_settings: 渲染设置

        Returns:
            nexrender 配置对象
        """
        config = {
            "template": {
                "src": template_path,
                "composition": data.get("composition", "Main"),
            },
            "output": {
                "src": output_path,
                "format": "mp4",
                "codec": "h264",
                "quality": 100,
            },
            "assets": [],
            "actions": [],
        }

        # 添加动态文本资产
        for key, value in data.items():
            if isinstance(value, str) and not key.startswith("_"):
                config["assets"].append({
                    "type": "data",
                    "layerName": key,
                    "property": "Source Text",
                    "value": value,
                })

        # 添加图片资产
        if "images" in data:
            for img_key, img_path in data["images"].items():
                config["assets"].append({
                    "type": "image",
                    "src": img_path,
                    "layerName": img_key,
                })

        # 添加音频资产
        if "audio" in data:
            config["assets"].append({
                "type": "audio",
                "src": data["audio"],
                "layerName": "Audio",
            })

        # 应用渲染设置覆盖
        if render_settings:
            config["output"].update(render_settings)

        return config

    def save_config(self, config: Dict[str, Any], config_path: str):
        """保存配置到文件"""
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    async def render(
        self,
        config: Dict[str, Any],
        config_path: Optional[str] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """执行 nexrender 渲染

        Args:
            config: nexrender 配置对象
            config_path: 配置文件路径（可选，自动生成）
            progress_callback: 进度回调函数

        Returns:
            渲染结果
        """
        import tempfile

        if not config_path:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                config_path = f.name

        try:
            cmd = f"{self.node_path} -e \"\nconst nexrender = require('nexrender');\nconst config = require('{config_path}');\n(async () => {{\n  try {{\n    const result = await nexrender.render(config);\n    console.log(JSON.stringify(result));\n  }} catch(e) {{\n    console.error('Error:', e.message);\n    process.exit(1);\n  }}\n}})();\n\""

            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode().strip() or stdout.decode().strip()
                logger.error(f"nexrender render failed: {error_msg}")
                return {"success": False, "error": error_msg}

            try:
                result = json.loads(stdout.decode())
                result["success"] = True
                return result
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "output": config["output"]["src"],
                    "stdout": stdout.decode(),
                }

        finally:
            if config_path and Path(config_path).exists():
                Path(config_path).unlink(missing_ok=True)

    async def batch_render(
        self,
        template_path: str,
        output_dir: str,
        data_list: List[Dict[str, Any]],
        render_settings: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """批量渲染模板

        Args:
            template_path: AE 模板路径
            output_dir: 输出目录
            data_list: 数据列表，每个元素对应一个渲染任务
            render_settings: 渲染设置

        Returns:
            批量渲染结果列表
        """
        results = []
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, data in enumerate(data_list):
            output_path = str(output_dir / f"output_{i:04d}.mp4")
            config = self.create_template_config(
                template_path=template_path,
                output_path=output_path,
                data=data,
                render_settings=render_settings,
            )
            result = await self.render(config)
            results.append(result)

            if i % 10 == 0:
                logger.info(f"Batch render progress: {i+1}/{len(data_list)}")

        return results

    def create_subtitle_template_config(
        self,
        template_path: str,
        output_path: str,
        subtitles: List[Dict[str, Any]],
        font_family: str = "Arial",
        font_size: int = 48,
        font_color: List[float] = None,
        glow_enabled: bool = True,
        glow_color: List[float] = None,
    ) -> Dict[str, Any]:
        """创建字幕模板渲染配置

        Args:
            template_path: AE 字幕模板路径
            output_path: 输出视频路径
            subtitles: 字幕列表
            font_family: 字体名称
            font_size: 字号
            font_color: 字体颜色
            glow_enabled: 是否启用发光
            glow_color: 发光颜色

        Returns:
            nexrender 配置对象
        """
        data = {
            "subtitles": json.dumps(subtitles),
            "fontFamily": font_family,
            "fontSize": font_size,
            "fontColor": font_color or [1, 1, 1],
            "glowEnabled": str(glow_enabled).lower(),
            "glowColor": glow_color or [0, 0.8, 1],
        }

        return self.create_template_config(
            template_path=template_path,
            output_path=output_path,
            data=data,
        )

    async def install_nexrender(self) -> bool:
        """安装 nexrender（如果未安装）"""
        logger.info("Installing nexrender...")
        try:
            proc = await asyncio.create_subprocess_shell(
                "npm install -g nexrender-cli",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.info("nexrender installed successfully")
                return True
            else:
                logger.error(f"Failed to install nexrender: {stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Install nexrender error: {e}")
            return False

    def get_template_variables(self, aep_path: str) -> List[str]:
        """从 AE 项目中提取可用的模板变量（图层名称）

        Args:
            aep_path: AE 项目文件路径

        Returns:
            图层名称列表（可作为模板变量）
        """
        variables = []
        try:
            import sys
            import importlib.machinery
            import importlib.util
            from pathlib import Path as _NxPath
            _project_root = _NxPath(__file__).resolve().parent.parent
            _pa_dir = _project_root / "puppet-automation"
            _src_dir = _pa_dir / "src"
            if "puppet_automation" not in sys.modules:
                _pkg = importlib.util.module_from_spec(
                    importlib.machinery.ModuleSpec(
                        "puppet_automation", loader=None, is_package=True
                    )
                )
                _pkg.__path__ = [str(_pa_dir)]
                sys.modules["puppet_automation"] = _pkg
            if "puppet_automation.src" not in sys.modules:
                _src_init = _src_dir / "__init__.py"
                if _src_init.exists():
                    _spec = importlib.util.spec_from_file_location(
                        "puppet_automation.src", _src_init,
                        submodule_search_locations=[str(_src_dir)]
                    )
                else:
                    _spec = importlib.machinery.ModuleSpec(
                        "puppet_automation.src", loader=None, is_package=True
                    )
                    _spec.submodule_search_locations = [str(_src_dir)]
                _src_pkg = importlib.util.module_from_spec(_spec)
                sys.modules["puppet_automation.src"] = _src_pkg
                if _spec.loader is not None:
                    _spec.loader.exec_module(_src_pkg)
            from puppet_automation.src.engines.ae.engine import AEEngine

            engine = AEEngine()
            comps = engine.list_compositions(aep_path)
            for comp in comps:
                layers = engine.list_layers(comp["name"], aep_path)
                for layer in layers:
                    if layer.get("type") == "TextLayer":
                        variables.append(layer["name"])
        except Exception as e:
            logger.warning(f"Failed to extract template variables: {e}")

        return variables


def get_nexrender_integration() -> NexrenderIntegration:
    """获取全局 nexrender 集成实例"""
    return NexrenderIntegration()


if __name__ == "__main__":
    import asyncio

    async def test():
        nexrender = NexrenderIntegration()
        available = await nexrender.is_available()
        print(f"Nexrender available: {available}")

        if not available:
            print("Installing nexrender...")
            success = await nexrender.install_nexrender()
            print(f"Installation success: {success}")

    asyncio.run(test())
