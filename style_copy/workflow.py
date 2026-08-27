#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
style_copy/workflow.py
视频风格智能复制工作流

完整流程:
  输入解析 → 风格分析 → 工具编排 → 执行 → 输出

复用项目:
  - input_parser.py
  - style_analyzer.py
  - tool_orchestrator.py
  - ffmpeg_generator.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from style_copy.input_parser import InputParser
from style_copy.style_analyzer import StyleAnalyzer, get_analyzer
from style_copy.tool_orchestrator import ToolOrchestrator
from style_copy.ffmpeg_generator import FFmpegCommandGenerator


class StyleCopyWorkflow:
    """视频风格智能复制工作流"""
    
    def __init__(self, work_dir: Optional[str] = None):
        self.work_dir = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="style_copy_"))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        self.parser = InputParser(str(self.work_dir))
        self.analyzer = get_analyzer()
        self.orchestrator = ToolOrchestrator()
        self.ffmpeg_generator = FFmpegCommandGenerator()
        
        self.state = {
            "step": "init",
            "success": False,
            "data": {}
        }
    
    def run(self, input_str: str) -> Dict:
        """执行完整工作流"""
        try:
            # Step 1: 输入解析
            self.state["step"] = "parsing"
            parse_result = self.parser.parse(input_str)
            if not parse_result["success"]:
                return {"success": False, "step": "parsing", "error": parse_result.get("error")}
            
            self.state["data"]["parse_result"] = parse_result
            
            # Step 2: 风格分析
            self.state["step"] = "analyzing"
            if parse_result["type"] == "url":
                style_result = self.analyzer.analyze_from_video(
                    parse_result["video_path"],
                    parse_result.get("keyframe_paths", [])
                )
            else:
                style_result = self.analyzer.analyze_from_prompt(parse_result["prompt"])
            
            if not style_result["success"]:
                return {"success": False, "step": "analyzing", "error": style_result.get("error")}
            
            self.state["data"]["style"] = style_result["style"]
            
            # Step 3: 工具编排
            self.state["step"] = "orchestrating"
            if parse_result["type"] == "url":
                video_path = parse_result["video_path"]
            else:
                video_path = ""
            
            tool_sequence = self.orchestrator.generate_tool_sequence(
                style_result["style"],
                video_path
            )
            
            if not tool_sequence["success"]:
                return {"success": False, "step": "orchestrating", "error": tool_sequence.get("error")}
            
            self.state["data"]["tool_sequence"] = tool_sequence["steps"]
            # 编排成功即视为流程成功：prompt 类型以 DAG 计划为产物；
            # url 类型会在下方 FFmpeg 执行后按真实出片结果覆盖 success。
            self.state["success"] = True

            # Step 4: 执行（简化版：先用FFmpeg执行）
            self.state["step"] = "executing"
            if parse_result["type"] == "url":
                output_path = str(self.work_dir / "output" / "final.mp4")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                try:
                    cmd = self.ffmpeg_generator.generate_command(
                        parse_result["video_path"],
                        output_path,
                        style_result["style"]
                    )
                    
                    self.state["data"]["ffmpeg_command"] = " ".join(cmd)
                    
                    import subprocess
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0 and os.path.exists(output_path):
                        self.state["data"]["output_path"] = output_path
                        self.state["success"] = True
                    else:
                        self.state["data"]["ffmpeg_error"] = result.stderr[:500] if result.stderr else "未知错误"
                        # fail-closed：FFmpeg 执行失败时不得标记整体成功（修复 fail-open 缺陷）
                        self.state["success"] = False
                        self.state["error"] = f"FFmpeg执行失败: {self.state['data']['ffmpeg_error']}"
                except Exception as e:
                    self.state["data"]["ffmpeg_error"] = str(e)
                    # fail-closed：同上
                    self.state["success"] = False
                    self.state["error"] = f"FFmpeg执行异常: {e}"
            
            self.state["step"] = "completed"
            return self.state
            
        except Exception as e:
            return {"success": False, "step": self.state["step"], "error": str(e)}


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  py -3.11 workflow.py <视频链接或提示词>")
        return
    
    input_str = " ".join(sys.argv[1:])
    
    print(f"开始执行风格复制工作流...")
    print(f"输入: {input_str[:50]}...")
    
    workflow = StyleCopyWorkflow()
    result = workflow.run(input_str)
    
    print("\n" + "="*50)
    print("工作流结果:")
    print("="*50)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()