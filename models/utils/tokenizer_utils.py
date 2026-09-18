"""
分词器工具集
提供分词器加载、编码、解码等工具函数，
支持多种分词器后端的优雅降级。
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TokenizerUtils:
    """分词器工具类
    
    提供统一的分词器接口，支持 HuggingFace tokenizers 和简单的字符级分词。
    所有外部依赖都有 try-except 保护，缺库时优雅降级。
    """
    
    def __init__(
        self,
        tokenizer_name_or_path: str = "",
        max_seq_length: int = 512,
        padding_side: str = "right",
        truncation_side: str = "right",
    ):
        """初始化分词器工具
        
        Args:
            tokenizer_name_or_path: 分词器名称或路径
            max_seq_length: 最大序列长度
            padding_side: padding 方向
            truncation_side: 截断方向
        """
        self.tokenizer_name_or_path = tokenizer_name_or_path
        self.max_seq_length = max_seq_length
        self.padding_side = padding_side
        self.truncation_side = truncation_side
        self._tokenizer = None
        self._backend = "none"
        self._vocab: dict[str, int] = {}
        self._inv_vocab: dict[int, str] = {}
        self._pad_token_id = 0
        self._eos_token_id = 1
        self._bos_token_id = 2
        self._unk_token_id = 3
        
        if tokenizer_name_or_path:
            self._load_tokenizer()
        else:
            self._build_simple_vocab()
            self._backend = "simple"
    
    def _load_tokenizer(self) -> None:
        """加载分词器，尝试多种后端"""
        try:
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(
                self.tokenizer_name_or_path,
                padding_side=self.padding_side,
                truncation_side=self.truncation_side,
            )
            self._backend = "transformers"
            self._pad_token_id = self._tokenizer.pad_token_id or 0
            self._eos_token_id = self._tokenizer.eos_token_id or 1
            self._bos_token_id = self._tokenizer.bos_token_id or 2
            self._unk_token_id = self._tokenizer.unk_token_id or 3
            logger.info(f"Loaded HuggingFace tokenizer: {self.tokenizer_name_or_path}")
            return
        except ImportError:
            logger.warning("transformers not available, trying simple tokenizer")
        except Exception as e:
            logger.warning(f"Failed to load HuggingFace tokenizer: {e}")
        
        self._build_simple_vocab()
        self._backend = "simple"
        logger.info("Using simple character-level tokenizer as fallback")
    
    def _build_simple_vocab(self) -> None:
        """构建简单的字符级词汇表"""
        vocab = {}
        
        special_tokens = ["[PAD]", "[EOS]", "[BOS]", "[UNK]"]
        for i, token in enumerate(special_tokens):
            vocab[token] = i
        
        chars = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        chars += "!@#$%^&*()_+-=[]{}|;':\",./<>?\\~`\n\t\r "
        chars += "varfunctionifelsereturnforwhilenewthisclass"
        chars += "applayereffectpropertyvaluetimecompitemproject"
        
        idx = len(special_tokens)
        for c in chars:
            if c not in vocab:
                vocab[c] = idx
                idx += 1
        
        self._vocab = vocab
        self._inv_vocab = {v: k for k, v in vocab.items()}
        self._pad_token_id = vocab["[PAD]"]
        self._eos_token_id = vocab["[EOS]"]
        self._bos_token_id = vocab["[BOS]"]
        self._unk_token_id = vocab["[UNK]"]
    
    @property
    def vocab_size(self) -> int:
        """词汇表大小"""
        if self._backend == "transformers" and self._tokenizer is not None:
            return self._tokenizer.vocab_size
        return len(self._vocab)
    
    @property
    def pad_token_id(self) -> int:
        """PAD token ID"""
        return self._pad_token_id
    
    @property
    def eos_token_id(self) -> int:
        """EOS token ID"""
        return self._eos_token_id
    
    @property
    def bos_token_id(self) -> int:
        """BOS token ID"""
        return self._bos_token_id
    
    @property
    def unk_token_id(self) -> int:
        """UNK token ID"""
        return self._unk_token_id
    
    @property
    def backend(self) -> str:
        """当前使用的分词器后端"""
        return self._backend
    
    def encode(
        self,
        text: str,
        add_special_tokens: bool = True,
        max_length: int | None = None,
        padding: bool = False,
        truncation: bool = True,
        return_tensors: str | None = None,
    ) -> dict[str, Any]:
        """编码文本为 token IDs
        
        Args:
            text: 输入文本
            add_special_tokens: 是否添加特殊 token
            max_length: 最大长度，默认使用初始化时的 max_seq_length
            padding: 是否 padding
            truncation: 是否截断
            return_tensors: 返回的张量类型（pt/np/none）
            
        Returns:
            Dict[str, Any]: 包含 input_ids 和 attention_mask
        """
        if max_length is None:
            max_length = self.max_seq_length
        
        if self._backend == "transformers" and self._tokenizer is not None:
            result = self._tokenizer(
                text,
                add_special_tokens=add_special_tokens,
                max_length=max_length,
                padding="max_length" if padding else False,
                truncation=truncation,
                return_tensors=return_tensors,
            )
            return {
                "input_ids": result["input_ids"],
                "attention_mask": result["attention_mask"],
            }
        
        return self._simple_encode(text, add_special_tokens, max_length, padding, truncation)
    
    def _simple_encode(
        self,
        text: str,
        add_special_tokens: bool,
        max_length: int,
        padding: bool,
        truncation: bool,
    ) -> dict[str, Any]:
        """简单的字符级编码
        
        Args:
            text: 输入文本
            add_special_tokens: 是否添加特殊 token
            max_length: 最大长度
            padding: 是否 padding
            truncation: 是否截断
            
        Returns:
            Dict[str, Any]: 包含 input_ids 和 attention_mask
        """
        tokens = []
        
        if add_special_tokens:
            tokens.append(self._bos_token_id)
        
        for c in text:
            tokens.append(self._vocab.get(c, self._unk_token_id))
        
        if add_special_tokens:
            tokens.append(self._eos_token_id)
        
        if truncation and len(tokens) > max_length:
            if self.truncation_side == "left":
                tokens = tokens[-max_length:]
            else:
                tokens = tokens[:max_length]
        
        attention_mask = [1] * len(tokens)
        
        if padding and len(tokens) < max_length:
            pad_len = max_length - len(tokens)
            if self.padding_side == "left":
                tokens = [self._pad_token_id] * pad_len + tokens
                attention_mask = [0] * pad_len + attention_mask
            else:
                tokens = tokens + [self._pad_token_id] * pad_len
                attention_mask = attention_mask + [0] * pad_len
        
        return {
            "input_ids": tokens,
            "attention_mask": attention_mask,
        }
    
    def decode(
        self,
        token_ids: list[int],
        skip_special_tokens: bool = True,
    ) -> str:
        """解码 token IDs 为文本
        
        Args:
            token_ids: token ID 列表
            skip_special_tokens: 是否跳过特殊 token
            
        Returns:
            str: 解码后的文本
        """
        if self._backend == "transformers" and self._tokenizer is not None:
            return self._tokenizer.decode(token_ids, skip_special_tokens=skip_special_tokens)
        
        return self._simple_decode(token_ids, skip_special_tokens)
    
    def _simple_decode(
        self,
        token_ids: list[int],
        skip_special_tokens: bool,
    ) -> str:
        """简单的字符级解码
        
        Args:
            token_ids: token ID 列表
            skip_special_tokens: 是否跳过特殊 token
            
        Returns:
            str: 解码后的文本
        """
        chars = []
        special_ids = {
            self._pad_token_id,
            self._eos_token_id,
            self._bos_token_id,
            self._unk_token_id,
        }
        
        for tid in token_ids:
            if skip_special_tokens and tid in special_ids:
                continue
            char = self._inv_vocab.get(tid, "")
            chars.append(char)
        
        return "".join(chars)
    
    def batch_encode(
        self,
        texts: list[str],
        add_special_tokens: bool = True,
        max_length: int | None = None,
        padding: bool = True,
        truncation: bool = True,
    ) -> dict[str, list]:
        """批量编码
        
        Args:
            texts: 文本列表
            add_special_tokens: 是否添加特殊 token
            max_length: 最大长度
            padding: 是否 padding
            truncation: 是否截断
            
        Returns:
            Dict[str, List]: 包含 input_ids 和 attention_mask 的列表
        """
        if max_length is None:
            max_length = self.max_seq_length
        
        all_input_ids = []
        all_attention_masks = []
        
        for text in texts:
            result = self.encode(
                text,
                add_special_tokens=add_special_tokens,
                max_length=max_length,
                padding=padding,
                truncation=truncation,
            )
            all_input_ids.append(result["input_ids"])
            all_attention_masks.append(result["attention_mask"])
        
        return {
            "input_ids": all_input_ids,
            "attention_mask": all_attention_masks,
        }
    
    def truncate_to_max_tokens(self, text: str, max_tokens: int) -> str:
        """将文本截断到指定 token 数量
        
        Args:
            text: 输入文本
            max_tokens: 最大 token 数
            
        Returns:
            str: 截断后的文本
        """
        encoded = self.encode(text, max_length=max_tokens, truncation=True)
        return self.decode(encoded["input_ids"])
    
    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数量
        
        Args:
            text: 输入文本
            
        Returns:
            int: token 数量
        """
        encoded = self.encode(text, add_special_tokens=False, truncation=False)
        if isinstance(encoded["input_ids"], list):
            return len(encoded["input_ids"])
        return encoded["input_ids"].shape[-1]
    
    def save_vocab(self, save_path: str) -> None:
        """保存词汇表到文件
        
        Args:
            save_path: 保存路径
        """
        vocab_data = {
            "vocab": self._vocab if self._backend == "simple" else {},
            "special_tokens": {
                "pad_token_id": self._pad_token_id,
                "eos_token_id": self._eos_token_id,
                "bos_token_id": self._bos_token_id,
                "unk_token_id": self._unk_token_id,
            },
            "backend": self._backend,
            "tokenizer_name": self.tokenizer_name_or_path,
        }
        
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(vocab_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Vocab saved to {save_path}")
    
    def load_vocab(self, load_path: str) -> None:
        """从文件加载词汇表
        
        Args:
            load_path: 加载路径
        """
        with open(load_path, "r", encoding="utf-8") as f:
            vocab_data = json.load(f)
        
        if "vocab" in vocab_data:
            self._vocab = vocab_data["vocab"]
            self._inv_vocab = {v: k for k, v in self._vocab.items()}
        
        if "special_tokens" in vocab_data:
            st = vocab_data["special_tokens"]
            self._pad_token_id = st.get("pad_token_id", 0)
            self._eos_token_id = st.get("eos_token_id", 1)
            self._bos_token_id = st.get("bos_token_id", 2)
            self._unk_token_id = st.get("unk_token_id", 3)
        
        self._backend = vocab_data.get("backend", "simple")
        logger.info(f"Vocab loaded from {load_path}")


def format_alpaca_prompt(
    instruction: str,
    input_text: str = "",
    output_text: str = "",
) -> str:
    """格式化 Alpaca 格式的 prompt
    
    Args:
        instruction: 指令
        input_text: 输入（可选）
        output_text: 输出（可选，用于训练）
        
    Returns:
        str: 格式化后的 prompt
    """
    prompt = f"### Instruction:\n{instruction}\n"
    
    if input_text:
        prompt += f"### Input:\n{input_text}\n"
    
    prompt += "### Response:\n"
    
    if output_text:
        prompt += output_text
    
    return prompt


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数量（不加载分词器）
    
    基于 1 token ≈ 4 字符的经验估算。
    
    Args:
        text: 输入文本
        
    Returns:
        int: 估算的 token 数
    """
    return max(1, len(text) // 4)
