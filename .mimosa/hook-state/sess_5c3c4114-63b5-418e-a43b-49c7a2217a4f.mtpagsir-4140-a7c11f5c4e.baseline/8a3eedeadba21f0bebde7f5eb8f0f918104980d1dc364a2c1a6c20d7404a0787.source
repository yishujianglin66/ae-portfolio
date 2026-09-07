"""
JSX 代码数据准备脚本 - 从项目中收集JSX代码并生成训练数据
参考 Antares 哲学：高质量垂直领域代码数据是小模型成功的关键
"""
import os
import json
import re
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

JSX_PATHS = [
    PROJECT_ROOT / "ae_additive_scripts",
    PROJECT_ROOT / "aep_analyzer" / "jsx",
    PROJECT_ROOT / "05-测试套件",
    PROJECT_ROOT / "external" / "F-s-PluginsProjects",
    PROJECT_ROOT / "AE-Scripts" / "ScriptUI Panels",
    PROJECT_ROOT / "archive" / "deprecated_self_built_bridge" / "ae-mcp-server" / "scripts",
]

SKIP_DIRS = [
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".ae-mcp-bridge",
    ".premiere-mcp-bridge",
]

SKIP_FILES = [
    "response_utils.jsx",
    "effect_utils.jsx",
    "comp_utils.jsx",
    "easing_utils.jsx",
    "args_loader.jsx",
]


class JSXDataCollector:
    """JSX代码数据收集器"""

    def __init__(self, output_dir: str = "./data/jsx"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.dataset: List[Dict[str, str]] = []
        self.style_descriptions = self._load_style_descriptions()

    def _load_style_descriptions(self) -> Dict[str, str]:
        """加载风格描述映射"""
        return {
            "applyExpression": "为图层属性添加表达式动画（wiggle、bounce、loop等效果）",
            "addTextLayerAdvanced": "创建高级艺术字图层，支持填充、描边、阴影、发光、变形、路径和3D效果",
            "applyColorCorrection": "对图层应用专业色彩校正效果（曲线、色阶、色相饱和度等）",
            "applyTextAnimation": "为文字图层添加动画效果",
            "applyTracker": "应用跟踪效果到图层",
            "apply3DComposition": "创建和配置3D合成",
            "addShapeLayer": "创建形状图层",
            "addTextLayer": "创建基础文字图层",
            "importFootage": "导入素材到项目",
            "batchAddEffects": "批量为多个图层添加效果",
            "addEffectWithKeyframes": "添加效果并设置关键帧",
            "setTrackMatte": "设置轨道遮罩",
            "setBlendMode": "设置图层混合模式",
            "addAdjustmentLayer": "添加调整图层",
            "createComposition": "创建新合成",
            "listCompositions": "列出所有合成",
            "executeAtomScript": "执行原子脚本",
            "batchApplySubtitles": "批量应用字幕",
            "trackedSubtitle": "创建带跟踪的字幕",
            "createSubtitleTemplate": "创建字幕模板",
            "artisticTextGenerator": "艺术字生成器",
            "textFXMaster": "文字特效主控",
            "stylizedTextFX": "风格化文字特效",
            "textAnimLibrary": "文字动画库",
            "expressionAnimLib": "表达式动画库",
            "textPresetCatalog": "文字预设目录",
            "textFXResourceIndex": "文字特效资源索引",
        }

    def collect_jsx_files(self) -> List[Path]:
        """收集项目中的所有JSX文件"""
        jsx_files = []
        
        for base_path in JSX_PATHS:
            if not base_path.exists():
                logger.warning(f"Path not found: {base_path}")
                continue
            
            for root, dirs, files in os.walk(base_path):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                
                for filename in files:
                    if filename.endswith(".jsx") and filename not in SKIP_FILES:
                        full_path = Path(root) / filename
                        jsx_files.append(full_path)
                        logger.debug(f"Found JSX: {full_path}")
        
        logger.info(f"Collected {len(jsx_files)} JSX files")
        return jsx_files

    def extract_function_blocks(self, jsx_content: str, filename: str) -> List[Tuple[str, str]]:
        """从JSX文件中提取函数块"""
        function_pattern = re.compile(
            r'function\s+(\w+)\s*\([^)]*\)\s*\{([\s\S]*?)\}',
            re.MULTILINE
        )
        
        matches = function_pattern.findall(jsx_content)
        results = []
        
        for func_name, func_body in matches:
            if len(func_body.strip()) > 50:
                full_func = f"function {func_name}() {{{func_body}}}"
                results.append((func_name, full_func))
        
        return results

    def parse_jsx_file(self, filepath: Path) -> Optional[Dict[str, str]]:
        """解析单个JSX文件"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            if len(content.strip()) < 50:
                return None
            
            filename = filepath.stem
            base_name = filename.replace("apply", "").replace("add", "").replace("create", "")
            
            instruction = self.style_descriptions.get(filename, "")
            if not instruction:
                instruction = self.style_descriptions.get(base_name, "")
            if not instruction:
                instruction = f"生成AE JSX脚本：{filepath.name}"
            
            functions = self.extract_function_blocks(content, filename)
            
            if functions:
                main_func_name = functions[0][0]
                code_parts = []
                
                for func_name, func_code in functions:
                    if len(func_code) < 5000:
                        code_parts.append(func_code)
                
                if code_parts:
                    code = "\n\n".join(code_parts)
                    return {
                        "instruction": instruction,
                        "input": f"脚本名称: {filepath.name}",
                        "output": code,
                        "source": str(filepath),
                        "function_name": main_func_name,
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse {filepath}: {e}")
            return None

    def build_dataset(self) -> List[Dict[str, str]]:
        """构建完整数据集"""
        jsx_files = self.collect_jsx_files()
        dataset = []
        
        for filepath in jsx_files:
            data = self.parse_jsx_file(filepath)
            if data:
                dataset.append(data)
                logger.info(f"Added: {data['function_name']} from {filepath.name}")
        
        self.dataset = dataset
        logger.info(f"Built dataset with {len(dataset)} samples")
        return dataset

    def generate_synthetic_samples(self, num_samples: int = 50) -> List[Dict[str, str]]:
        """生成合成样本（基于模板扩展）"""
        templates = [
            {
                "instruction": "为图层添加wiggle表达式动画",
                "input": "合成名称: MyComp, 图层索引: 1, 属性: Position, 频率: 2, 幅度: 50",
                "output": """function applyWiggle(args) {
    var comp = app.project.itemByName(args.compName);
    var layer = comp.layer(args.layerIndex);
    var prop = layer.property(args.property);
    var freq = args.frequency || 2;
    var amount = args.amount || 50;
    prop.expression = "wiggle(" + freq + ", " + amount + ");";
    return { success: true };
}""",
            },
            {
                "instruction": "创建新合成",
                "input": "名称: NewComp, 宽度: 1920, 高度: 1080, 时长: 10秒, 帧率: 25",
                "output": """function createComp(args) {
    var width = args.width || 1920;
    var height = args.height || 1080;
    var duration = args.duration || 10;
    var fps = args.fps || 25;
    var comp = app.project.items.addComp(
        args.name || "NewComp",
        width, height, 1, duration, fps
    );
    return { compName: comp.name, compIndex: comp.index };
}""",
            },
            {
                "instruction": "添加发光效果",
                "input": "合成名称: MyComp, 图层索引: 1, 颜色: [1, 0.5, 0], 半径: 20",
                "output": """function applyGlow(args) {
    var comp = app.project.itemByName(args.compName);
    var layer = comp.layer(args.layerIndex);
    var glow = layer.Effects.addProperty("ADBE Glo2i");
    glow.property("ADBE Glo2i-0001").setValue(args.color || [1, 0.5, 0]);
    glow.property("ADBE Glo2i-0002").setValue(args.radius || 20);
    glow.property("ADBE Glo2i-0003").setValue(args.intensity || 1);
    return { success: true };
}""",
            },
            {
                "instruction": "设置关键帧动画",
                "input": "合成名称: MyComp, 图层索引: 1, 属性: Position, 起始值: [960, 540], 结束值: [960, 300], 时长: 2秒",
                "output": """function setKeyframes(args) {
    var comp = app.project.itemByName(args.compName);
    var layer = comp.layer(args.layerIndex);
    var prop = layer.property(args.property);
    var startTime = args.startTime || 0;
    var endTime = args.endTime || 2;
    
    prop.setValueAtTime(startTime, args.startValue);
    prop.setValueAtTime(endTime, args.endValue);
    
    return { success: true, keyframesAdded: 2 };
}""",
            },
            {
                "instruction": "批量处理图层",
                "input": "合成名称: MyComp, 效果类型: Glow",
                "output": """function batchApplyEffect(args) {
    var comp = app.project.itemByName(args.compName);
    var appliedCount = 0;
    
    for (var i = 1; i <= comp.numLayers; i++) {
        var layer = comp.layer(i);
        try {
            layer.Effects.addProperty(args.effectType);
            appliedCount++;
        } catch (e) {}
    }
    
    return { success: true, appliedTo: appliedCount + " layers" };
}""",
            },
        ]
        
        synthetic = []
        for i in range(num_samples):
            template = templates[i % len(templates)]
            variation = {
                "instruction": template["instruction"],
                "input": template["input"],
                "output": template["output"],
                "source": "synthetic",
                "function_name": f"generated_{i}",
            }
            synthetic.append(variation)
        
        return synthetic

    def save_dataset(self, filename: str = "jsx_code_dataset.jsonl") -> str:
        """保存数据集到JSONL文件"""
        filepath = self.output_dir / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            for item in self.dataset:
                line = json.dumps(item, ensure_ascii=False)
                f.write(line + "\n")
        
        logger.info(f"Dataset saved to {filepath}")
        return str(filepath)

    def save_stats(self) -> None:
        """保存数据集统计信息"""
        stats = {
            "total_samples": len(self.dataset),
            "sources": {},
            "function_names": [],
        }
        
        for item in self.dataset:
            source = item.get("source", "unknown")
            if source not in stats["sources"]:
                stats["sources"][source] = 0
            stats["sources"][source] += 1
            stats["function_names"].append(item.get("function_name", "unknown"))
        
        stats_file = self.output_dir / "dataset_stats.json"
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Stats saved to {stats_file}")


def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    collector = JSXDataCollector()
    
    logger.info("=== Building JSX dataset ===")
    collector.build_dataset()
    
    logger.info("=== Adding synthetic samples ===")
    synthetic = collector.generate_synthetic_samples(100)
    collector.dataset.extend(synthetic)
    
    logger.info(f"=== Total samples: {len(collector.dataset)} ===")
    
    collector.save_dataset()
    collector.save_stats()
    
    logger.info("=== Dataset preparation complete ===")


if __name__ == "__main__":
    main()