#!/usr/bin/env python3
"""
深度分析 AE 2025 插件资源完整性，生成补全方案
调用 LLM 网关进行智能分析
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def analyze_ae_resources():
    """调用 LLM 分析 AE 资源完整性"""
    from core.llm_gateway import chat_with_routing, TaskType

    # 读取扫描结果
    ae_scan_path = Path("D:/AE-Work/ae25_plugin_scan.txt")
    resource_scan_path = Path("D:/AE-Work/resource_library_scan.txt")

    ae_scan = ae_scan_path.read_text(encoding="utf-8") if ae_scan_path.exists() else "N/A"
    resource_scan = resource_scan_path.read_text(encoding="utf-8") if resource_scan_path.exists() else "N/A"

    system_prompt = """你是一位资深 After Effects 资源管理专家和视频制作工作流架构师。
你精通 AE 插件生态（Red Giant、Boris FX、Video Copilot、Trapcode、Sapphire、Continuum 等）、
脚本开发、预设管理、LUT 调色、字体管理和资源库构建。

请根据提供的扫描数据进行深度分析并输出结构化的补全方案。"""

    user_prompt = f"""以下是 Adobe After Effects 2025 v25.3 的资源扫描结果：

=== AE 2025 安装扫描（前200行摘要）===
{ae_scan[:3000]}

=== 资源库扫描（完整）===
{resource_scan}

=== 项目配置 ===
AE 2025 路径: C:/Program Files/Adobe/Adobe After Effects 2025
资源库根目录: D:/AE-Work/resources
AE 工程文件目录: D:/AE-Work/projects
项目代码库: c:/Users/Administrator/Desktop/AE-Knowledge-Vault

请完成以下任务：

1. **深度评估 AE 2025 插件完整性**：
   - 已安装的 2217 个插件覆盖了哪些类别？（粒子、光效、抠像、调色、跟踪、稳定、3D、转场、文字动画、卡通特效等）
   - 哪些重要插件缺失或只有空文件夹（如 Trapcode 目录 0 个插件）？
   - 有哪些常见的 AE 必备插件套装还没有？

2. **资源库缺失分析**：
   - resources 目录下哪些类别完全缺失？（plugins、scripts、presets、effects、videos、images、templates 等）
   - 已有的类别（fonts、luts、audio、presets空目录、effects空目录）是否足够？还需要补充什么？

3. **项目配置补全建议**：
   - AE 脚本如何与 puppet-automation 引擎层对接？
   - 资源索引服务是否需要新增类别？
   - 还需要配置哪些路径和环境变量？

4. **优先级排序**：P0（必须立即补全）、P1（重要）、P2（可选增强）

请用清晰的中文 Markdown 格式输出，包含具体的补全建议和操作步骤。"""

    print("正在调用 LLM 进行深度分析...")
    response = await chat_with_routing(
        user_prompt,
        task_type=TaskType.GENERAL,
        system_prompt=system_prompt,
        temperature=0.3,
    )

    if response.success:
        output_path = Path("D:/AE-Work/ae_resource_analysis.md")
        output_path.write_text(response.content, encoding="utf-8")
        print(f"分析完成，结果已保存到: {output_path}")
        print(f"Token 用量: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
        return response.content
    else:
        print(f"LLM 调用失败: {response.error}")
        return None


if __name__ == "__main__":
    asyncio.run(analyze_ae_resources())
