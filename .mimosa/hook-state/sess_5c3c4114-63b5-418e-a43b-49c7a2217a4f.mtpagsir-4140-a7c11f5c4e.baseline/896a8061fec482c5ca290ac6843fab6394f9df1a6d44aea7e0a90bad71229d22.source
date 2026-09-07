#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成手机端友好的 Word 文档 - AE-Knowledge-Vault 项目进度总览
基于 2026-07-22 开发文档 + 2026-07-21 系列文档汇总
"""

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

OUTPUT_PATH = r"D:\AE-Work\AE-Vault-项目进度总览-手机版.docx"


def set_cell_shading(cell, fill_color):
    """设置单元格背景色"""
    shading = cell._element.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), fill_color)
    shd.set(qn('w:val'), 'clear')
    shading.append(shd)


def set_cell_font(cell, text, font_size=12, bold=False, color=None):
    """设置单元格字体"""
    cell.text = ""
    p = cell.paragraphs[0]
    run = p.add_run(text)
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_heading(doc, text, level=1, color=None):
    """添加标题（手机端大字体）"""
    sizes = {1: 20, 2: 16, 3: 14}
    size = sizes.get(level, 14)
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = True
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if color:
        run.font.color.rgb = RGBColor(*color)
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_body(doc, text, size=13, bold=False, color=None):
    """添加正文段落"""
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    if color:
        run.font.color.rgb = RGBColor(*color)
    p.paragraph_format.space_after = Pt(4)
    return p


def add_bullet(doc, text, size=13):
    """添加项目符号段落"""
    p = doc.add_paragraph(style='List Bullet')
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    p.paragraph_format.space_after = Pt(2)
    return p


def add_table(doc, headers, rows):
    """添加表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = 'Table Grid'
    # 表头
    for i, h in enumerate(headers):
        set_cell_font(table.rows[0].cells[i], h, font_size=12, bold=True, color=(255, 255, 255))
        set_cell_shading(table.rows[0].cells[i], '2980B9')
    # 数据行
    for r_idx, row_data in enumerate(rows):
        for c_idx, cell_text in enumerate(row_data):
            set_cell_font(table.rows[r_idx + 1].cells[c_idx], str(cell_text), font_size=11)
    return table


def build_document():
    doc = Document()

    # 全局字体设置
    style = doc.styles['Normal']
    style.font.name = '微软雅黑'
    style.font.size = Pt(13)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 页边距（窄边距，适合手机）
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(1.5)
        section.right_margin = Cm(1.5)

    # === 封面标题 ===
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run("AE-Knowledge-Vault\n项目进度总览")
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    run.font.color.rgb = RGBColor(41, 128, 185)

    add_body(doc, "", size=6)
    add_body(doc, "更新日期：2026-07-22", size=13, bold=True)
    add_body(doc, "本文档为手机端优化版本", size=12, color=(128, 128, 128))

    # === 目录概要 ===
    add_heading(doc, "目录概要", level=1, color=(41, 128, 185))
    toc_items = [
        "1. 项目总览与当前状态",
        "2. 今日核心成果（渲染修复）",
        "3. AE 2025 效果 API 兼容性",
        "4. Bridge 通信架构",
        "5. V2 增强版工程计划",
        "6. DaVinci Resolve 引擎状态",
        "7. AE 脚本库完整清单",
        "8. 后续开发路线图",
        "9. 关键经验教训",
    ]
    for item in toc_items:
        add_body(doc, item, size=13, bold=True)

    # === 1. 项目总览 ===
    add_heading(doc, "一、项目总览与当前状态", level=1, color=(41, 128, 185))

    add_body(doc, "核心目标", size=14, bold=True, color=(192, 80, 77))
    add_body(doc, "构建一套完整的视频自动化生产系统，涵盖 AE 特效制作、PR 剪辑、DaVinci 调色、PS 图像处理的全链路自动化能力。")

    add_body(doc, "", size=4)
    add_body(doc, "当前整体状态", size=14, bold=True, color=(192, 80, 77))

    status_rows = [
        ["AE 引擎", "✅ 可用", "39 个 JSX 脚本，完整 Bridge 协议"],
        ["DaVinci 引擎", "✅ 可用", "ResolveColorEngine v4.0，12 预设"],
        ["PR 引擎", "❌ 待开发", "Python 客户端完成，无 JSX 脚本"],
        ["PS 引擎", "❌ 待开发", "Python 客户端完成，无 JSX 脚本"],
        ["AU 引擎", "❌ 待开发", "ExtendScript 支持有限"],
        ["Bridge 协议", "✅ 稳定", "文件轮询 + 自动重试 + 健康监控"],
        ["可观测性", "✅ 完整", "全链路追踪 + 指标导出 + 健康评分"],
        ["测试覆盖", "✅ 319 通过", "9 个跳过（需真实环境）"],
    ]
    add_table(doc, ["模块", "状态", "说明"], status_rows)

    # === 2. 今日核心成果 ===
    add_heading(doc, "二、今日核心成果（2026-07-22）", level=1, color=(41, 128, 185))

    add_body(doc, "渲染黑屏问题已修复", size=14, bold=True, color=(192, 80, 77))
    add_body(doc, "问题：aerender 渲染输出全黑（仅 83KB）")
    add_body(doc, "原因：工程图层结构不完整，文字图层缺失")
    add_body(doc, "解决方案：通过 rebuild_textfx.py 重建工程")
    add_body(doc, "结果：输出正常 MP4（3.13 MB），不再黑屏", bold=True, color=(0, 128, 0))

    add_body(doc, "", size=4)
    add_body(doc, "输出文件", size=14, bold=True)
    output_rows = [
        ["测试版", "D:/AE-Work/TextFX_Showcase_Test.mp4", "3.13 MB", "✅ 正常"],
        ["正式版", "D:/AE-Work/TextFX_Showcase_Final.mp4", "3.13 MB", "✅ 正常"],
    ]
    add_table(doc, ["版本", "路径", "大小", "状态"], output_rows)

    add_body(doc, "", size=4)
    add_body(doc, "渲染命令（已验证可用）", size=14, bold=True)
    add_body(doc, 'aerender -project "D:\\AE-Work\\TextFX_Showcase.aep" -comp "TextFX_Showcase" -output "D:\\AE-Work\\TextFX_Showcase_Final.mp4"', size=11)

    # === 3. AE 2025 效果 API ===
    add_heading(doc, "三、AE 2025 效果 API 兼容性", level=1, color=(41, 128, 185))

    add_body(doc, "已验证可用效果", size=14, bold=True, color=(0, 128, 0))
    avail_rows = [
        ["发光", "Glow / ADBE Glo2", "✅ 可用"],
        ["渐变", "Ramp", "✅ 可用（需 try-catch）"],
        ["文字图层", "Text Layer", "✅ 可用"],
        ["固态层", "Solid", "✅ 可用"],
    ]
    add_table(doc, ["效果", "API 名称", "状态"], avail_rows)

    add_body(doc, "", size=4)
    add_body(doc, "待验证效果", size=14, bold=True, color=(192, 80, 77))
    pending_rows = [
        ["高斯模糊", "Gaussian Blur", "⚠️ 待测试"],
        ["镜头光晕", "Lens Flare", "⚠️ 待测试"],
        ["分形噪波", "Fractal Noise", "⚠️ 待测试"],
        ["色阶", "Levels", "⚠️ 待测试"],
        ["色相/饱和度", "Hue/Saturation", "⚠️ 待测试"],
        ["网格", "Grid", "⚠️ 待测试"],
        ["粗糙边缘", "Roughen Edges", "⚠️ 待测试"],
        ["扭曲", "Turbulent Displace", "⚠️ 待测试"],
    ]
    add_table(doc, ["效果", "API 名称", "状态"], pending_rows)

    add_body(doc, "", size=4)
    add_body(doc, "AE 2025 API 兼容性问题总结", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "layer.effects 返回 undefined → 直接调用 layer.effects.add()")
    add_bullet(doc, "效果名称中英文不兼容 → try-catch 尝试多种名称")
    add_bullet(doc, "参数范围与文档不符 → 用 Math.max/min 限制范围")
    add_bullet(doc, "Ramp 颜色格式问题 → try-catch 包裹 setValue")
    add_bullet(doc, "$.evalFile() 大文件崩溃 → 用 eval(code) 代替")

    # === 4. Bridge 通信 ===
    add_heading(doc, "四、Bridge 通信架构", level=1, color=(41, 128, 185))

    add_body(doc, "通信流程", size=14, bold=True)
    add_body(doc, "Python 客户端 → 写命令 JSON → Bridge 监听 → AE 执行 JSX → 写结果 JSON → Python 读取结果")

    add_body(doc, "", size=4)
    add_body(doc, "关键文件", size=14, bold=True)
    bridge_rows = [
        [".ae-mcp-bridge/2_mcp_bridge_loader.jsx", "Bridge 小面板源码（533行）"],
        [".ae-mcp-bridge/z_mcp_bridge_startup.jsx", "AE 启动自动加载脚本"],
        [".ae-mcp-bridge/ae_command.json", "命令文件"],
        [".ae-mcp-bridge/ae_result.json", "结果文件"],
        [".ae-mcp-bridge/ae_auto_listener.log", "执行日志"],
    ]
    add_table(doc, ["文件", "说明"], bridge_rows)

    add_body(doc, "", size=4)
    add_body(doc, "自动启动配置", size=14, bold=True)
    add_body(doc, "已将启动脚本复制到 AE Startup 文件夹：")
    add_body(doc, "C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\Scripts\\Startup\\z_mcp_bridge_startup.jsx", size=11)
    add_body(doc, "效果：AE 启动时自动加载 Bridge，无需手动操作。", color=(0, 128, 0))

    # === 5. V2 增强版 ===
    add_heading(doc, "五、V2 增强版工程计划", level=1, color=(41, 128, 185))

    add_body(doc, "目标架构", size=14, bold=True)
    add_body(doc, "TextFX Showcase V2 合成结构：")
    add_bullet(doc, "调整图层（调色/晕影）")
    add_bullet(doc, "前景图层（装饰/遮罩）")
    add_bullet(doc, "主体文字图层（6场景）")
    add_bullet(doc, "装饰图层（网格/噪波/光晕）")
    add_bullet(doc, "背景图层（渐变/固态）")
    add_bullet(doc, "3D 摄像机 + 灯光（待添加）")

    add_body(doc, "", size=4)
    add_body(doc, "场景增强计划", size=14, bold=True)
    scene_rows = [
        ["S1 Cyber", "✅ 基础版", "网格背景、扭曲入场动画"],
        ["S2 Ink", "✅ 基础版", "粗糙边缘、模糊效果"],
        ["S3 Neon", "✅ 基础版", "分形噪波背景、镜头光晕"],
        ["S4 Holo", "✅ 基础版", "双重投影、色相偏移"],
        ["S5 Fire/Ice", "✅ 基础版", "渐变背景、混合模式"],
        ["S6 Logo", "✅ 基础版", "调色调整层、光晕效果"],
    ]
    add_table(doc, ["场景", "当前", "增强目标"], scene_rows)

    # === 6. DaVinci 引擎 ===
    add_heading(doc, "六、DaVinci Resolve 引擎状态", level=1, color=(41, 128, 185))

    add_body(doc, "当前版本：ResolveColorEngine v4.0", size=14, bold=True, color=(0, 128, 0))
    add_body(doc, "执行路径：fuscript.exe + Lua（唯一可靠路径）")

    add_body(doc, "", size=4)
    add_body(doc, "核心能力", size=14, bold=True)
    davinci_rows = [
        ["全自动调色", "auto_grade()", "启动→创建→导入→调色→渲染→关闭"],
        ["一键调色", "quick_grade()", "Resolve 不可用时自动 FFmpeg 降级"],
        ["12 预设", "apply_preset_config()", "ghibli/premium/clean/flat/dramatic 等"],
        ["Fusion 调色", "apply_fusion()", "Brightness/Contrast/Saturation"],
        ["FFmpeg 降级", "ffmpeg_grade()", "7 个预设，无需 Resolve"],
        ["场景检测", "detect_scenes()", "PySceneDetect 自动检测"],
        ["分段调色", "auto_segment_presets()", "检测+自动分配预设"],
        ["跨软件互通", "build_artifact()", "ColorGradeArtifact"],
    ]
    add_table(doc, ["能力", "方法", "说明"], davinci_rows)

    # === 7. AE 脚本库 ===
    add_heading(doc, "七、AE 脚本库完整清单（39个）", level=1, color=(41, 128, 185))

    add_body(doc, "Phase 5-1 核心功能（新增 4 个）", size=14, bold=True, color=(0, 128, 0))
    add_bullet(doc, "applyTracker.jsx — 动态追踪（点/稳定/角点/平面）")
    add_bullet(doc, "applyColorCorrection.jsx — 高级色彩校正（7种工具）")
    add_bullet(doc, "apply3DComposition.jsx — 3D 合成（灯光/摄像机/景深）")
    add_bullet(doc, "applyExpression.jsx — 表达式控制（8种类型）")

    add_body(doc, "", size=4)
    add_body(doc, "Phase 5-2 文字系统（新增 5 个）", size=14, bold=True, color=(0, 128, 0))
    add_bullet(doc, "addTextLayerAdvanced.jsx — 高级艺术字（填充/描边/阴影/发光/变形/路径/3D）")
    add_bullet(doc, "applyTextAnimation.jsx — 文字动画（10种动画类型）")
    add_bullet(doc, "createSubtitleTemplate.jsx — 花样字幕模板（7种风格）")
    add_bullet(doc, "trackedSubtitle.jsx — 动态追踪字幕（4种追踪模式）")
    add_bullet(doc, "batchApplySubtitles.jsx — 批量字幕（JSON/SRT/ASS）")

    add_body(doc, "", size=4)
    add_body(doc, "Phase 1-4 基础库（30 个）", size=14, bold=True)
    add_bullet(doc, "基础图层：addTextLayer / addShapeLayer / addAdjustmentLayer / addCamera / addLight / addPrecomp / importFootage")
    add_bullet(doc, "动画效果：addEffectWithKeyframes / setEffectKeyframes / setKeyframeEasing / setMotionBlur / enableTimeRemap / applyNewtonDynamics")
    add_bullet(doc, "遮罩混合：addMaskWithShape / setBlendMode / setTrackMatte / setParentLayer")
    add_bullet(doc, "颜色管理：applyLUT")
    add_bullet(doc, "第三方插件：applyParticular / applySaber / applyOpticalFlares")
    add_bullet(doc, "端到端：createE2EMusicVideo / executeAtomScript")

    # === 8. 路线图 ===
    add_heading(doc, "八、后续开发路线图", level=1, color=(41, 128, 185))

    add_body(doc, "立即（效果增强）", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "1. 逐个验证 AE 2025 可用效果清单")
    add_bullet(doc, "2. 启用 V2 增强版工程，添加高级效果")
    add_bullet(doc, "3. 每添加一个效果就测试渲染，确保不黑屏")

    add_body(doc, "", size=4)
    add_body(doc, "短期（特效系统）", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "4. 封装常用特效组合生成器（cyberGlow/neonEffect/hologramEffect 等）")
    add_bullet(doc, "5. 添加 3D 摄像机 + 灯光系统")
    add_bullet(doc, "6. 添加调整图层（调色/晕影）")

    add_body(doc, "", size=4)
    add_body(doc, "中期（产品化）", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "7. 将流程封装为一键命令")
    add_bullet(doc, "8. 支持自定义文字/颜色/时长参数")
    add_bullet(doc, "9. 批量生成不同风格的展示视频")

    add_body(doc, "", size=4)
    add_body(doc, "长期（能力展示）", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "10. 整合 79 种动画 + 4998 预设的完整能力展示")
    add_bullet(doc, "11. 对接 DaVinci Resolve 调色流程")
    add_bullet(doc, "12. 形成可复用的视频自动化生产模板")

    # === 9. 经验教训 ===
    add_heading(doc, "九、关键经验教训", level=1, color=(41, 128, 185))

    add_body(doc, "本次实战核心教训", size=14, bold=True, color=(192, 80, 77))
    add_bullet(doc, "AE 预览 ≠ 渲染输出：GUI 看起来正常不代表 aerender 输出正常")
    add_bullet(doc, "先简后繁：先用最简 JSX 验证全流程，再逐步添加复杂效果")
    add_bullet(doc, "图层缺失导致黑屏：原工程仅 1 个图层是黑屏根本原因")
    add_bullet(doc, "AE 2025 效果 API 不可信：文档参数范围与实际不符，必须 try-catch")
    add_bullet(doc, "Bridge 自动加载需配置：Startup 脚本是实现自动加载的关键")
    add_bullet(doc, "效果名称兼容性：同一效果可能有英文/中文/matchName 三种名称")

    # === 环境检查 ===
    add_heading(doc, "十、新会话快速启动指南", level=1, color=(41, 128, 185))

    add_body(doc, "环境检查清单", size=14, bold=True)
    add_bullet(doc, "AE 是否运行：Get-Process -Name AfterFX")
    add_bullet(doc, "Bridge 是否响应：py -3.12 scripts/quick_test.py")
    add_bullet(doc, "工程文件是否存在：Test-Path D:\\AE-Work\\TextFX_Showcase.aep")
    add_bullet(doc, "渲染输出是否存在：Test-Path D:\\AE-Work\\TextFX_Showcase_Final.mp4")

    add_body(doc, "", size=4)
    add_body(doc, "关键约束", size=14, bold=True)
    add_bullet(doc, "使用小面板 Bridge（.ae-mcp-bridge/2_mcp_bridge_loader.jsx）执行 JSX")
    add_bullet(doc, "AE 2025 不支持 aerender -rjsx")
    add_bullet(doc, "Python 用 py -3.12 执行")

    # === 页脚 ===
    add_body(doc, "", size=8)
    footer_p = doc.add_paragraph()
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run("— AE-Knowledge-Vault 项目 —")
    run.font.size = Pt(10)
    run.font.color.rgb = RGBColor(128, 128, 128)
    run.font.name = "微软雅黑"
    run._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 保存
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc.save(OUTPUT_PATH)
    print(f"Word 文档已生成：{OUTPUT_PATH}")
    print(f"文件大小：{os.path.getsize(OUTPUT_PATH) / 1024:.1f} KB")


if __name__ == "__main__":
    build_document()
