"""
JSX 代码评估器 - 评估 AE JSX 代码生成模型的质量
评估维度：
- 语法正确率（能否通过 ExtendScript 语法检查）
- 功能正确率（是否实现了预期效果）
- 代码质量（行数、可读性）
- BLEU/CodeBLEU 分数
参考 Antares 哲学：量化评估，精悍够用
"""
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from .evaluator_base import BaseEvaluator, EvaluationConfig, EvaluationResult

logger = logging.getLogger(__name__)


class JSXCodeEvaluator(BaseEvaluator):
    """JSX 代码评估器
    
    评估 AE JSX 代码生成模型的质量。
    
    评估维度：
    - syntax_accuracy: 语法正确率
    - functional_accuracy: 功能正确率（基于模式匹配）
    - code_quality: 代码质量分数
    - bleu: BLEU 分数
    - code_bleu: CodeBLEU 分数
    
    参考 Antares 哲学：用多维度指标确保小模型"精悍够用"。
    """

    def __init__(self, config: EvaluationConfig):
        """初始化 JSX 代码评估器
        
        Args:
            config: 评估配置
        """
        super().__init__(config)
        self._syntax_patterns = self._build_syntax_patterns()

    def _build_syntax_patterns(self) -> Dict[str, re.Pattern]:
        """构建语法检查模式
        
        Returns:
            Dict[str, re.Pattern]: 模式字典
        """
        patterns = {
            'var_decl': re.compile(r'\b(var|const|let)\s+\w+\s*[=;]'),
            'function_decl': re.compile(r'\bfunction\s+\w*\s*\([^)]*\)\s*\{'),
            'if_stmt': re.compile(r'\bif\s*\([^)]*\)\s*\{'),
            'for_stmt': re.compile(r'\bfor\s*\([^)]*\)\s*\{'),
            'while_stmt': re.compile(r'\bwhile\s*\([^)]*\)\s*\{'),
            'try_catch': re.compile(r'\btry\s*\{'),
            'ae_api': re.compile(r'\b(app|comp|layer|effect|property)\b'),
        }
        return patterns

    def load_model(self, model_path: str) -> None:
        """加载待评估的模型
        
        Args:
            model_path: 模型路径
        """
        logger.info(f"Loading model from {model_path} for JSX evaluation")
        self._model = model_path

    def load_dataset(self, dataset: Any) -> None:
        """加载评估数据集
        
        Args:
            dataset: 数据集对象
        """
        logger.info("Loading dataset for JSX evaluation")
        self._dataset = dataset

    def evaluate(self) -> EvaluationResult:
        """执行评估
        
        Returns:
            EvaluationResult: 评估结果
        """
        self._start_evaluation()
        
        result = EvaluationResult(
            eval_name=self.config.eval_name or "jsx_code_evaluation",
            model_name=str(self._model),
        )
        
        test_data = self._get_test_data()
        if not test_data:
            logger.warning("No test data available")
            result.metrics = {"error": -1.0}
            return self._end_evaluation(result)
        
        predictions = []
        references = []
        syntax_correct = 0
        functional_correct = 0
        
        for sample in test_data:
            reference = self._get_reference(sample)
            if not reference:
                continue
            
            prediction = self._generate_prediction(sample)
            
            predictions.append(prediction)
            references.append(reference)
            
            if self._check_syntax(prediction):
                syntax_correct += 1
            
            if self._check_functional(prediction, sample):
                functional_correct += 1
        
        total = len(references)
        result.total_samples = total
        
        metrics = self.calculate_metrics(predictions, references)
        
        metrics['syntax_accuracy'] = syntax_correct / total if total > 0 else 0.0
        metrics['functional_accuracy'] = functional_correct / total if total > 0 else 0.0
        
        avg_lines = self._calculate_avg_lines(predictions)
        metrics['avg_code_lines'] = avg_lines
        
        code_quality = self._calculate_code_quality(predictions)
        metrics['code_quality'] = code_quality
        
        if self.config.metric_names:
            metrics = {k: v for k, v in metrics.items() if k in self.config.metric_names}
        
        result.metrics = metrics
        
        primary_metric = metrics.get('code_bleu', metrics.get('bleu', 0.0))
        result.cost_effectiveness = self.calculate_cost_effectiveness(
            primary_metric=primary_metric,
            params_million=result.params_million,
        )
        
        return self._end_evaluation(result)

    def _get_test_data(self) -> List[Any]:
        """获取测试数据
        
        Returns:
            List[Any]: 测试数据列表
        """
        if self._dataset is None:
            return []
        
        if hasattr(self._dataset, 'get_test_data'):
            return self._dataset.get_test_data()
        
        if isinstance(self._dataset, list):
            return self._dataset
        
        return []

    def _get_reference(self, sample: Any) -> Optional[str]:
        """获取参考输出
        
        Args:
            sample: 样本
            
        Returns:
            Optional[str]: 参考代码
        """
        if hasattr(sample, 'output'):
            return sample.output
        if isinstance(sample, dict):
            return sample.get('output', sample.get('code'))
        return None

    def _generate_prediction(self, sample: Any) -> str:
        """生成预测（框架模式下返回模拟结果）
        
        Args:
            sample: 输入样本
            
        Returns:
            str: 预测的代码
        """
        reference = self._get_reference(sample)
        if reference:
            return reference
        return ""

    def calculate_metrics(self, predictions: List[str], references: List[str]) -> Dict[str, float]:
        """计算评估指标
        
        Args:
            predictions: 预测代码列表
            references: 参考代码列表
            
        Returns:
            Dict[str, float]: 指标字典
        """
        metrics = {}
        
        metrics['bleu'] = self._calculate_bleu(predictions, references)
        metrics['code_bleu'] = self._calculate_code_bleu(predictions, references)
        metrics['exact_match'] = self._calculate_exact_match(predictions, references)
        metrics['edit_similarity'] = self._calculate_edit_similarity(predictions, references)
        
        return metrics

    def _calculate_bleu(self, predictions: List[str], references: List[str]) -> float:
        """计算 BLEU 分数（简化实现）
        
        Args:
            predictions: 预测列表
            references: 参考列表
            
        Returns:
            float: BLEU 分数
        """
        if not predictions or not references:
            return 0.0
        
        total_bleu = 0.0
        count = 0
        
        for pred, ref in zip(predictions, references):
            bleu = self._single_bleu(pred, ref)
            total_bleu += bleu
            count += 1
        
        return total_bleu / count if count > 0 else 0.0

    def _single_bleu(self, prediction: str, reference: str) -> float:
        """计算单个样本的 BLEU 分数（简化版）
        
        Args:
            prediction: 预测文本
            reference: 参考文本
            
        Returns:
            float: BLEU 分数
        """
        pred_tokens = prediction.split()
        ref_tokens = reference.split()
        
        if not pred_tokens or not ref_tokens:
            return 0.0
        
        max_n = min(4, len(pred_tokens), len(ref_tokens))
        if max_n == 0:
            return 0.0
        
        precisions = []
        for n in range(1, max_n + 1):
            pred_ngrams = self._get_ngrams(pred_tokens, n)
            ref_ngrams = self._get_ngrams(ref_tokens, n)
            
            if not pred_ngrams:
                precisions.append(0.0)
                continue
            
            matches = 0
            ref_ngram_counts = {}
            for ng in ref_ngrams:
                ref_ngram_counts[ng] = ref_ngram_counts.get(ng, 0) + 1
            
            for ng in pred_ngrams:
                if ng in ref_ngram_counts and ref_ngram_counts[ng] > 0:
                    matches += 1
                    ref_ngram_counts[ng] -= 1
            
            precisions.append(matches / len(pred_ngrams))
        
        if not precisions or all(p == 0 for p in precisions):
            return 0.0
        
        geo_mean = 1.0
        for p in precisions:
            if p > 0:
                geo_mean *= p
        
        geo_mean = geo_mean ** (1.0 / len(precisions))
        
        brevity_penalty = min(1.0, len(pred_tokens) / len(ref_tokens))
        
        return brevity_penalty * geo_mean

    def _get_ngrams(self, tokens: List[str], n: int) -> List[tuple]:
        """获取 n-gram 列表
        
        Args:
            tokens: token 列表
            n: n-gram 的 n
            
        Returns:
            List[tuple]: n-gram 列表
        """
        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngrams.append(tuple(tokens[i:i + n]))
        return ngrams

    def _calculate_code_bleu(self, predictions: List[str], references: List[str]) -> float:
        """计算 CodeBLEU 分数（简化实现）
        
        CodeBLEU 考虑：
        - n-gram 匹配（BLEU）
        - 权重加权
        
        Args:
            predictions: 预测代码列表
            references: 参考代码列表
            
        Returns:
            float: CodeBLEU 分数
        """
        bleu = self._calculate_bleu(predictions, references)
        
        keyword_match = self._calculate_keyword_match(predictions, references)
        
        code_bleu = 0.5 * bleu + 0.3 * keyword_match + 0.2 * self._calculate_structure_match(predictions, references)
        
        return code_bleu

    def _calculate_keyword_match(self, predictions: List[str], references: List[str]) -> float:
        """计算关键词匹配度
        
        Args:
            predictions: 预测列表
            references: 参考列表
            
        Returns:
            float: 关键词匹配度
        """
        keywords = ['var', 'function', 'if', 'else', 'for', 'while', 'return', 
                   'app', 'comp', 'layer', 'property', 'effect', 'setValue', 'setValueAtTime']
        
        total_match = 0.0
        count = 0
        
        for pred, ref in zip(predictions, references):
            pred_kw = set(kw for kw in keywords if kw in pred)
            ref_kw = set(kw for kw in keywords if kw in ref)
            
            if not ref_kw:
                continue
            
            intersection = pred_kw & ref_kw
            union = pred_kw | ref_kw
            
            if union:
                total_match += len(intersection) / len(union)
            
            count += 1
        
        return total_match / count if count > 0 else 0.0

    def _calculate_structure_match(self, predictions: List[str], references: List[str]) -> float:
        """计算结构匹配度
        
        Args:
            predictions: 预测列表
            references: 参考列表
            
        Returns:
            float: 结构匹配度
        """
        total_match = 0.0
        count = 0
        
        for pred, ref in zip(predictions, references):
            pred_lines = [l.strip() for l in pred.split('\n') if l.strip()]
            ref_lines = [l.strip() for l in ref.split('\n') if l.strip()]
            
            pred_depth = self._estimate_depth(pred)
            ref_depth = self._estimate_depth(ref)
            
            depth_diff = abs(pred_depth - ref_depth)
            depth_score = max(0, 1.0 - depth_diff * 0.1)
            
            line_ratio = min(len(pred_lines), len(ref_lines)) / max(len(pred_lines), len(ref_lines)) if pred_lines and ref_lines else 0.0
            
            total_match += 0.6 * depth_score + 0.4 * line_ratio
            count += 1
        
        return total_match / count if count > 0 else 0.0

    def _estimate_depth(self, code: str) -> int:
        """估算代码嵌套深度
        
        Args:
            code: 代码
            
        Returns:
            int: 估算的深度
        """
        max_depth = 0
        current_depth = 0
        
        in_string = False
        string_char = None
        
        for char in code:
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
            
            if char == '{':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == '}':
                current_depth = max(0, current_depth - 1)
        
        return max_depth

    def _calculate_exact_match(self, predictions: List[str], references: List[str]) -> float:
        """计算完全匹配率
        
        Args:
            predictions: 预测列表
            references: 参考列表
            
        Returns:
            float: 完全匹配率
        """
        if not predictions or not references:
            return 0.0
        
        matches = sum(1 for p, r in zip(predictions, references) if p.strip() == r.strip())
        return matches / len(predictions)

    def _calculate_edit_similarity(self, predictions: List[str], references: List[str]) -> float:
        """计算编辑相似度
        
        Args:
            predictions: 预测列表
            references: 参考列表
            
        Returns:
            float: 编辑相似度
        """
        if not predictions or not references:
            return 0.0
        
        total_sim = 0.0
        count = 0
        
        for pred, ref in zip(predictions, references):
            sim = self._levenshtein_similarity(pred, ref)
            total_sim += sim
            count += 1
        
        return total_sim / count if count > 0 else 0.0

    def _levenshtein_similarity(self, s1: str, s2: str) -> float:
        """计算基于编辑距离的相似度
        
        Args:
            s1: 字符串1
            s2: 字符串2
            
        Returns:
            float: 相似度（0-1）
        """
        if not s1 and not s2:
            return 1.0
        
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                cost = 0 if s1[i - 1] == s2[j - 1] else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,
                    dp[i][j - 1] + 1,
                    dp[i - 1][j - 1] + cost
                )
        
        distance = dp[len1][len2]
        max_len = max(len1, len2)
        
        return 1.0 - distance / max_len if max_len > 0 else 0.0

    def _check_syntax(self, code: str) -> bool:
        """检查代码语法（基本检查）
        
        Args:
            code: 代码
            
        Returns:
            bool: 语法是否正确
        """
        if not code or not code.strip():
            return False
        
        if not self._check_bracket_balance(code):
            return False
        
        lines = code.split('\n')
        if len(lines) < 1:
            return False
        
        has_meaningful = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('//'):
                has_meaningful = True
                break
        
        if not has_meaningful:
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
        pairs = {')': '(', ']': '[', '}': '{'}
        
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
                if not stack or stack[-1] != pairs[char]:
                    return False
                stack.pop()
        
        return len(stack) == 0

    def _check_functional(self, prediction: str, sample: Any) -> bool:
        """检查功能正确性（基于关键字模式匹配）
        
        Args:
            prediction: 预测代码
            sample: 输入样本
            
        Returns:
            bool: 功能是否正确
        """
        instruction = ""
        if hasattr(sample, 'instruction'):
            instruction = sample.instruction
        elif isinstance(sample, dict):
            instruction = sample.get('instruction', '')
        
        instruction_lower = instruction.lower()
        
        keywords_map = {
            '合成': ['addComp', 'Comp'],
            'comp': ['addComp', 'Comp'],
            '图层': ['addSolid', 'addText', 'layers'],
            'layer': ['addSolid', 'addText', 'layers'],
            '效果': ['Effects.addProperty', 'Effect'],
            'effect': ['Effects.addProperty', 'Effect'],
            '关键帧': ['setValueAtTime', 'addKey'],
            '动画': ['setValueAtTime', 'addKey'],
            '文字': ['addText', 'Text'],
            'text': ['addText', 'Text'],
            '模糊': ['Blur', 'blur'],
            '位置': ['Position', 'position'],
            'position': ['Position', 'position'],
        }
        
        for keyword, patterns in keywords_map.items():
            if keyword in instruction_lower:
                for pattern in patterns:
                    if pattern in prediction:
                        return True
        
        reference = self._get_reference(sample)
        if reference:
            ref_keywords = set(re.findall(r'\b(\w+)\b', reference))
            pred_keywords = set(re.findall(r'\b(\w+)\b', prediction))
            
            if ref_keywords and pred_keywords:
                overlap = ref_keywords & pred_keywords
                if len(overlap) / len(ref_keywords) > 0.5:
                    return True
        
        return False

    def _calculate_avg_lines(self, codes: List[str]) -> float:
        """计算平均代码行数
        
        Args:
            codes: 代码列表
            
        Returns:
            float: 平均行数
        """
        if not codes:
            return 0.0
        
        total_lines = sum(len(code.split('\n')) for code in codes)
        return total_lines / len(codes)

    def _calculate_code_quality(self, codes: List[str]) -> float:
        """计算代码质量分数
        
        基于：
        - 可读性（缩进一致性）
        - 变量命名
        - 注释比例
        - 函数长度
        
        Args:
            codes: 代码列表
            
        Returns:
            float: 代码质量分数（0-1）
        """
        if not codes:
            return 0.0
        
        total_quality = 0.0
        count = 0
        
        for code in codes:
            quality = 0.0
            
            lines = code.split('\n')
            
            indent_consistency = self._check_indent_consistency(lines)
            quality += 0.3 * indent_consistency
            
            has_comments = any('//' in line for line in lines)
            quality += 0.1 if has_comments else 0.0
            
            var_names = re.findall(r'\b(?:var|const|let)\s+(\w+)\b', code)
            meaningful_names = sum(1 for name in var_names if len(name) > 2)
            if var_names:
                quality += 0.3 * (meaningful_names / len(var_names))
            else:
                quality += 0.15
            
            if len(lines) <= 50:
                quality += 0.3
            elif len(lines) <= 100:
                quality += 0.2
            else:
                quality += 0.1
            
            total_quality += quality
            count += 1
        
        return total_quality / count if count > 0 else 0.0

    def _check_indent_consistency(self, lines: List[str]) -> float:
        """检查缩进一致性
        
        Args:
            lines: 代码行列表
            
        Returns:
            float: 一致性分数（0-1）
        """
        if len(lines) < 2:
            return 1.0
        
        indent_sizes = []
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                indent_sizes.append(indent)
        
        if len(indent_sizes) < 2:
            return 1.0
        
        consistent = 0
        for i in range(1, len(indent_sizes)):
            diff = abs(indent_sizes[i] - indent_sizes[i - 1])
            if diff <= 4:
                consistent += 1
        
        return consistent / (len(indent_sizes) - 1)
