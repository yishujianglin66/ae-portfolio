"""
JSX 代码数据集 - 用于 AE JSX 代码生成小模型
数据格式：{ "instruction": "...", "input": "...", "output": "..." }
支持数据增强和语法校验过滤
参考 Antares 哲学：高质量垂直领域代码数据是小模型成功的关键
"""
import json
import os
import re
import random
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .dataset_base import BaseDataset, DatasetConfig, DatasetStats

logger = logging.getLogger(__name__)


@dataclass
class JSXSample:
    """JSX 代码样本"""
    instruction: str
    """指令/需求描述"""
    input: str
    """输入上下文（可选）"""
    output: str
    """输出的 JSX 代码"""
    metadata: Dict[str, Any] = None
    """元数据"""

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class JSXCodeDataset(BaseDataset):
    """JSX 代码数据集
    
    用于训练 AE JSX 代码生成小模型。
    支持：
    - 从 JSONL 文件加载
    - 数据增强（变量名替换、注释添加/删除等）
    - 语法校验过滤
    
    参考 Antares 哲学：高质量、经过校验的代码数据 > 大量低质量数据
    """

    def __init__(self, config: DatasetConfig):
        """初始化 JSX 代码数据集
        
        Args:
            config: 数据集配置
        """
        super().__init__(config)
        self._variable_patterns = [
            r'\bvar\s+(\w+)\b',
            r'\bconst\s+(\w+)\b',
            r'\blet\s+(\w+)\b',
            r'function\s+(\w+)\s*\(',
        ]

    def load_data(self, data_path: str) -> List[JSXSample]:
        """从 JSONL 文件加载 JSX 代码数据
        
        Args:
            data_path: JSONL 文件路径或目录
            
        Returns:
            List[JSXSample]: 样本列表
        """
        samples = []
        
        if os.path.isdir(data_path):
            for filename in os.listdir(data_path):
                if filename.endswith('.jsonl') or filename.endswith('.json'):
                    filepath = os.path.join(data_path, filename)
                    samples.extend(self._load_file(filepath))
        else:
            samples.extend(self._load_file(data_path))
        
        return samples

    def _load_file(self, filepath: str) -> List[JSXSample]:
        """加载单个文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            List[JSXSample]: 样本列表
        """
        samples = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if filepath.endswith('.jsonl'):
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            sample = self._dict_to_sample(data)
                            if sample:
                                samples.append(sample)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON parse error at line {line_num}: {e}")
                else:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            sample = self._dict_to_sample(item)
                            if sample:
                                samples.append(sample)
                    else:
                        sample = self._dict_to_sample(data)
                        if sample:
                            samples.append(sample)
        except Exception as e:
            logger.error(f"Failed to load file {filepath}: {e}")
        
        return samples

    def _dict_to_sample(self, data: Dict[str, Any]) -> Optional[JSXSample]:
        """将字典转换为 JSXSample
        
        Args:
            data: 数据字典
            
        Returns:
            Optional[JSXSample]: 样本对象，格式错误返回 None
        """
        try:
            instruction = data.get('instruction', data.get('prompt', ''))
            input_text = data.get('input', data.get('context', ''))
            output = data.get('output', data.get('code', data.get('response', '')))
            
            if not instruction or not output:
                return None
            
            metadata = {k: v for k, v in data.items() 
                       if k not in ('instruction', 'input', 'output', 'prompt', 'context', 'code', 'response')}
            
            return JSXSample(
                instruction=instruction,
                input=input_text,
                output=output,
                metadata=metadata
            )
        except Exception:
            return None

    def preprocess(self, data: List[JSXSample]) -> List[JSXSample]:
        """数据预处理
        
        清理代码格式，标准化缩进等。
        
        Args:
            data: 原始数据
            
        Returns:
            List[JSXSample]: 预处理后的数据
        """
        processed = []
        
        for sample in data:
            try:
                cleaned_output = self._clean_code(sample.output)
                cleaned_instruction = sample.instruction.strip()
                cleaned_input = sample.input.strip() if sample.input else ""
                
                processed_sample = JSXSample(
                    instruction=cleaned_instruction,
                    input=cleaned_input,
                    output=cleaned_output,
                    metadata=sample.metadata.copy()
                )
                processed.append(processed_sample)
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}")
        
        return processed

    def _clean_code(self, code: str) -> str:
        """清理代码格式
        
        Args:
            code: 原始代码
            
        Returns:
            str: 清理后的代码
        """
        lines = code.split('\n')
        cleaned_lines = []
        
        for line in lines:
            cleaned = line.rstrip()
            cleaned_lines.append(cleaned)
        
        while cleaned_lines and not cleaned_lines[0].strip():
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1].strip():
            cleaned_lines.pop()
        
        return '\n'.join(cleaned_lines)

    def validate_sample(self, sample: JSXSample) -> bool:
        """验证样本是否有效
        
        进行基本的 JSX 语法校验。
        
        Args:
            sample: 单个样本
            
        Returns:
            bool: 样本是否有效
        """
        if not isinstance(sample, JSXSample):
            return False
        
        if not sample.output or len(sample.output.strip()) < 10:
            return False
        
        code = sample.output
        
        if not self._check_bracket_balance(code):
            return False
        
        if 'app.beginUndoGroup' in code and 'app.endUndoGroup' not in code:
            return False
        
        if len(code) > 10000:
            return False
        
        return True

    def _check_bracket_balance(self, code: str) -> bool:
        """检查括号平衡
        
        Args:
            code: 代码
            
        Returns:
            bool: 括号是否平衡
        """
        stack = []
        bracket_pairs = {')': '(', ']': '[', '}': '{'}
        
        in_string = False
        string_char = None
        escape_next = False
        
        for char in code:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\' and in_string:
                escape_next = True
                continue
            
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
                continue
            elif char == string_char and in_string:
                in_string = False
                string_char = None
                continue
            
            if in_string:
                continue
            
            if char in '([{':
                stack.append(char)
            elif char in ')]}':
                if not stack or stack[-1] != bracket_pairs[char]:
                    return False
                stack.pop()
        
        return len(stack) == 0

    def augment_sample(self, sample: JSXSample) -> List[JSXSample]:
        """数据增强 - 从单个样本生成多个变体
        
        增强策略：
        - 变量名替换
        - 注释添加/删除
        - 代码格式微调
        
        Args:
            sample: 单个样本
            
        Returns:
            List[JSXSample]: 增强后的样本列表
        """
        augmented = []
        
        if random.random() < 0.5:
            var_renamed = self._rename_variables(sample)
            if var_renamed:
                augmented.append(var_renamed)
        
        if random.random() < 0.3:
            comment_added = self._add_comments(sample)
            if comment_added:
                augmented.append(comment_added)
        
        if random.random() < 0.3:
            comment_removed = self._remove_comments(sample)
            if comment_removed:
                augmented.append(comment_removed)
        
        return augmented

    def _rename_variables(self, sample: JSXSample) -> Optional[JSXSample]:
        """变量名替换增强
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[JSXSample]: 变量重命名后的样本
        """
        try:
            code = sample.output
            var_names = set()
            
            for pattern in self._variable_patterns:
                matches = re.findall(pattern, code)
                var_names.update(matches)
            
            var_names = [v for v in var_names if v not in ('app', 'this', 'true', 'false', 'null')]
            
            if len(var_names) < 2:
                return None
            
            rename_map = {}
            suffix = f"_{random.randint(100, 999)}"
            for var in var_names:
                rename_map[var] = var + suffix
            
            new_code = code
            for old_name, new_name in rename_map.items():
                pattern = r'\b' + re.escape(old_name) + r'\b'
                new_code = re.sub(pattern, new_name, new_code)
            
            return JSXSample(
                instruction=sample.instruction,
                input=sample.input,
                output=new_code,
                metadata={**sample.metadata, 'augmented': 'var_rename'}
            )
        except Exception as e:
            logger.warning(f"Variable rename augmentation failed: {e}")
            return None

    def _add_comments(self, sample: JSXSample) -> Optional[JSXSample]:
        """添加注释增强
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[JSXSample]: 添加注释后的样本
        """
        try:
            code = sample.output
            lines = code.split('\n')
            
            if len(lines) < 5:
                return None
            
            comment_lines = [
                "// Apply effect to the selected layer",
                "// Create a new composition",
                "// Set up the animation parameters",
                "// Loop through all layers",
                "// Get the active composition",
            ]
            
            new_lines = lines.copy()
            insert_positions = random.sample(range(len(new_lines)), min(2, len(new_lines)))
            
            for pos in sorted(insert_positions, reverse=True):
                comment = random.choice(comment_lines)
                indent = len(new_lines[pos]) - len(new_lines[pos].lstrip())
                new_lines.insert(pos, ' ' * indent + comment)
            
            new_code = '\n'.join(new_lines)
            
            return JSXSample(
                instruction=sample.instruction,
                input=sample.input,
                output=new_code,
                metadata={**sample.metadata, 'augmented': 'add_comments'}
            )
        except Exception as e:
            logger.warning(f"Add comments augmentation failed: {e}")
            return None

    def _remove_comments(self, sample: JSXSample) -> Optional[JSXSample]:
        """删除注释增强
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[JSXSample]: 删除注释后的样本
        """
        try:
            code = sample.output
            
            if '//' not in code:
                return None
            
            new_lines = []
            for line in code.split('\n'):
                stripped = line.strip()
                if stripped.startswith('//'):
                    continue
                if '//' in line:
                    line = line[:line.index('//')].rstrip()
                new_lines.append(line)
            
            new_code = '\n'.join(new_lines)
            
            if len(new_code.strip()) < 10:
                return None
            
            return JSXSample(
                instruction=sample.instruction,
                input=sample.input,
                output=new_code,
                metadata={**sample.metadata, 'augmented': 'remove_comments'}
            )
        except Exception as e:
            logger.warning(f"Remove comments augmentation failed: {e}")
            return None

    def to_huggingface_dataset(self):
        """转换为 HuggingFace 数据集格式（如果可用）
        
        Returns:
            数据集对象或 None
        """
        try:
            from datasets import Dataset
            
            train_data = [
                {
                    'instruction': s.instruction,
                    'input': s.input,
                    'output': s.output,
                }
                for s in self._train_data
            ]
            
            return Dataset.from_list(train_data)
        except ImportError:
            logger.warning("datasets library not available")
            return None
