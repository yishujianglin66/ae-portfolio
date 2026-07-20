#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V4 顾问 - DeepSeek V4 集成顾问
==============================

我(M3助手)的「外脑」- 用于需要深度推理的任务。

何时调用我:
1. 复杂项目分析/架构评估
2. 知识库智能问答（V4有1M上下文）
3. 自然语言到工具调用的翻译
4. 代码审查/质量分析

使用方法:
    # 1. 设置环境变量
    $env:DEEPSEEK_API_KEY = "sk-your-key"
    
    # 2. 运行
    py -3.11 v4_advisor.py "你的问题"
    
    # 或交互式
    py -3.11 v4_advisor.py --chat
"""

import os
import sys
import json
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("请先安装 requests: py -3.11 -m pip install requests")
    sys.exit(1)

# ============================================================================
# 配置
# ============================================================================

API_BASE = "https://api.deepseek.com"
FLASH_MODEL = "deepseek-v4-flash"  # ¥1/百万字，日常用
PRO_MODEL = "deepseek-v4-pro"      # ¥3/百万字，重要决策

SYSTEM_PROMPT = """你是「M3助手的V4顾问」。

你的角色:
- 你是M3助手的外脑，专精深度推理和长文本处理
- M3擅长工具调用和文件操作，你擅长复杂分析
- 你的输出会被M3整合后呈现给用户

工作原则:
1. 中文回答，结构化输出（Markdown）
2. 先给结论，再给推理过程
3. 涉及代码时给出可执行示例
4. 涉及架构时考虑成本和可维护性
5. 不知道的事情直接说，不要编造

当前项目背景:
- 项目: AE-Knowledge-Vault (企业级AE知识库系统)
- 规模: 777个文档, 35个工具, 11个软件引擎
- 技术栈: FastAPI + React + 工具链集成
- 你的能力: 1M上下文, Tool Calls, 推理模式
"""


class V4Advisor:
    """V4顾问 - 简单直接"""

    def __init__(self):
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            print("❌ 错误: 未设置 DEEPSEEK_API_KEY 环境变量")
            print("\n请先设置:")
            print('  PowerShell: $env:DEEPSEEK_API_KEY = "sk-your-key"')
            print('  CMD: set DEEPSEEK_API_KEY=sk-your-key')
            sys.exit(1)
        
        self.history = []
        self.total_tokens = 0

    def ask(self, question: str, model: str = "pro", use_reasoning: bool = True) -> str:
        """问V4一个问题（默认Pro模型，效果优先）"""
        model_name = PRO_MODEL if model != "flash" else FLASH_MODEL
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": question})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        
        if model == "flash" and use_reasoning:
            payload["reasoning_effort"] = "high"

        start = time.time()
        try:
            response = requests.post(
                f"{API_BASE}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            result = response.json()
            
            duration = time.time() - start
            
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                self.history.append({"role": "user", "content": question})
                self.history.append({"role": "assistant", "content": content})
                
                # 统计
                if "usage" in result:
                    usage = result["usage"]
                    self.total_tokens += usage.get("total_tokens", 0)
                    cost = self._calc_cost(usage, model_name)
                    print(f"\n[模型: {model_name} | 耗时: {duration:.1f}s | Token: {usage.get('total_tokens', 0)} | 预估费用: ¥{cost:.4f}]")
                
                return content
            else:
                return f"API返回异常: {result}"
                
        except requests.exceptions.HTTPError as e:
            return f"HTTP错误: {e}\n响应: {e.response.text if e.response else 'N/A'}"
        except Exception as e:
            return f"请求失败: {e}"

    def _calc_cost(self, usage: dict, model: str) -> float:
        """计算费用"""
        if "pro" in model:
            in_price, out_price = 3, 6
        else:
            in_price, out_price = 1, 2
        
        prompt = usage.get("prompt_tokens", 0) / 1_000_000
        completion = usage.get("completion_tokens", 0) / 1_000_000
        return prompt * in_price + completion * out_price

    def chat_loop(self):
        """交互式对话"""
        print("=" * 60)
        print("V4 顾问 - 交互模式")
        print("=" * 60)
        print("命令: /pro 切换Pro | /flash 切换Flash | /clear 清空 | /exit 退出")
        print("=" * 60 + "\n")
        print("💡 默认使用 Pro 模型 (效果优先)")
        print("=" * 60 + "\n")
        
        model = "pro"
        while True:
            try:
                user_input = input(f"[{model.upper()}] 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见!")
                break
            
            if not user_input:
                continue
            
            if user_input == "/exit":
                break
            elif user_input == "/pro":
                model = "pro"
                print(f"→ 已切换到 Pro 模型\n")
                continue
            elif user_input == "/flash":
                model = "flash"
                print(f"→ 已切换到 Flash 模型\n")
                continue
            elif user_input == "/clear":
                self.history = []
                print("→ 对话历史已清空\n")
                continue
            
            print("\nV4 思考中...")
            answer = self.ask(user_input, model=model)
            print(f"\nV4: {answer}\n")


# ============================================================================
# 快捷方法 - 给我自己(M3)用的
# ============================================================================

def quick_analyze(topic: str) -> str:
    """快速分析 - 给我自己用的封装"""
    advisor = V4Advisor()
    return advisor.ask(f"请分析以下问题，给出结构化结论:\n\n{topic}", model="pro")


def quick_qa(question: str, use_flash: bool = False) -> str:
    """快速问答 - 默认Pro模型（效果优先）
    
    Args:
        question: 问题
        use_flash: 是否使用Flash（仅简单事实问答时设为True）
    """
    advisor = V4Advisor()
    return advisor.ask(question, model="flash" if use_flash else "pro")


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    cmd = sys.argv[1]
    
    if cmd == "--chat" or cmd == "-c":
        V4Advisor().chat_loop()
    elif cmd == "--analyze" or cmd == "-a":
        topic = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "请分析当前项目"
        print(quick_analyze(topic))
    elif cmd == "--qa" or cmd == "-q":
        question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "你好"
        print(quick_qa(question))
    elif cmd == "--help" or cmd == "-h":
        print(__doc__)
    else:
        # 直接问问题
        question = " ".join(sys.argv[1:])
        advisor = V4Advisor()
        answer = advisor.ask(question)
        print(answer)


if __name__ == "__main__":
    main()