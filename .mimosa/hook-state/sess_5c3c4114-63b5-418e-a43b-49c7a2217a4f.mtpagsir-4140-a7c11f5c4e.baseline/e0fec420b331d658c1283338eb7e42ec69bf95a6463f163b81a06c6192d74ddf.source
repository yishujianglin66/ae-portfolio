"""
魔搭社区 ModelScope 统一集成入口
=====================================
将魔搭社区的视频分析、风格识别、向量检索等能力统一封装，
与AE自动化管线无缝对接。

使用示例：
    from integrations.modelscope_integration import ModelScopeIntegration

    ms = ModelScopeIntegration()
    
    # 分析素材视频
    result = ms.analyze_material("path/to/material.mp4")
    
    # 搜索相关知识
    knowledge = ms.search_knowledge("赛博朋克风格")
    
    # 生成AI素材
    image = ms.generate_material("futuristic cityscape, neon lights")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .modelscope_skills import ModelScopeSkillsClient, VideoAnalysisResult
from .modelscope_vector_search import KnowledgeBaseSearcher, SearchResult


class ModelScopeIntegration:
    """
    魔搭社区统一集成类
    
    整合视频分析、风格识别、向量检索、文生图等功能，
    为AE自动化管线提供AI增强能力。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        kb_root: Optional[str] = None,
    ):
        """
        初始化魔搭集成
        
        Args:
            api_key: ModelScope API Key（默认从环境变量读取）
            kb_root: 知识库根目录路径
        """
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        
        if not self.api_key:
            raise ValueError(
                "未找到MODELSCOPE_API_KEY。"
                "请在.env文件中设置，或作为参数传入。"
            )
        
        # 初始化各模块
        self.skills_client = ModelScopeSkillsClient(api_key=self.api_key)
        self.kb_searcher = KnowledgeBaseSearcher(
            api_key=self.api_key,
            kb_root=kb_root,
        )
        
        print("✓ 魔搭社区集成初始化完成")
    
    def analyze_material(
        self,
        video_path: str,
        analysis_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """
        分析AE素材视频
        
        Args:
            video_path: 视频文件路径
            analysis_type: 分析类型
        
        Returns:
            分析结果字典
        """
        print(f"📹 分析素材: {video_path}")
        
        # 视频内容分析
        video_result = self.skills_client.analyze_video(video_path, analysis_type)
        
        # 风格匹配
        style_match = self.skills_client.match_style_to_templates(
            video_result.style_tags
        )
        
        # 搜索相关知识
        knowledge = self.search_knowledge(
            f"{' '.join(video_result.style_tags)} 风格特效"
        )
        
        return {
            "video_analysis": video_result.to_dict(),
            "style_match": {
                "templates": style_match.matched_templates,
                "confidence": style_match.confidence,
                "suggestions": style_match.suggestions,
            },
            "related_knowledge": [r.to_dict() for r in knowledge],
        }
    
    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """
        搜索风格化剪辑知识库
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
        
        Returns:
            搜索结果列表
        """
        return self.kb_searcher.search(query, top_k=top_k)
    
    def generate_material(
        self,
        prompt: str,
        style: str = "auto",
        size: str = "1920x1080",
    ) -> Dict[str, Any]:
        """
        AI生成素材（文生图）
        
        Args:
            prompt: 提示词
            style: 风格预设
            size: 图片尺寸
        
        Returns:
            生成结果
        """
        print(f"🎨 生成素材: {prompt[:50]}...")
        
        result = self.skills_client.generate_image(
            prompt=prompt,
            style=style,
            size=size,
        )
        
        return result
    
    def batch_analyze_materials(
        self,
        material_dir: str,
        output_dir: Optional[str] = None,
        file_pattern: str = "*.mp4",
    ) -> List[Dict[str, Any]]:
        """
        批量分析素材目录
        
        Args:
            material_dir: 素材目录路径
            output_dir: 结果输出目录
            file_pattern: 文件匹配模式
        
        Returns:
            分析结果列表
        """
        material_path = Path(material_dir)
        
        if not material_path.exists():
            print(f"⚠ 素材目录不存在: {material_dir}")
            return []
        
        video_files = list(material_path.glob(file_pattern))
        print(f"📂 找到 {len(video_files)} 个素材文件")
        
        results = []
        
        for i, video_file in enumerate(video_files, 1):
            print(f"\n[{i}/{len(video_files)}] 处理: {video_file.name}")
            
            try:
                result = self.analyze_material(str(video_file))
                results.append(result)
            except Exception as e:
                print(f"  ✗ 分析失败: {e}")
                results.append({"error": str(e), "video": str(video_file)})
        
        # 保存汇总结果
        if output_dir and results:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            
            summary_file = out_path / "analysis_summary.json"
            with open(summary_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            print(f"\n✓ 汇总结果已保存: {summary_file}")
        
        return results
    
    def build_knowledge_index(self):
        """构建知识库向量索引"""
        print("🔨 构建知识库索引...")
        self.kb_searcher.build_index()
        print("✓ 索引构建完成")
    
    def get_integration_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            "api_key_configured": bool(self.api_key),
            "api_key_prefix": self.api_key[:8] + "..." if self.api_key else "",
            "kb_root": str(self.kb_searcher.kb_root),
            "kb_documents": len(self.kb_searcher.documents),
            "kb_indexed": len(self.kb_searcher.embeddings),
            "modules": {
                "skills_client": "✓" if self.skills_client else "✗",
                "kb_searcher": "✓" if self.kb_searcher else "",
            }
        }


# 便捷函数
def create_integration(
    api_key: Optional[str] = None,
    kb_root: Optional[str] = None,
) -> ModelScopeIntegration:
    """创建魔搭集成实例"""
    return ModelScopeIntegration(api_key=api_key, kb_root=kb_root)


if __name__ == "__main__":
    print("=" * 60)
    print("魔搭社区 ModelScope 统一集成测试")
    print("=" * 60)
    
    try:
        ms = create_integration()
        
        # 显示集成状态
        print("\n集成状态:")
        status = ms.get_integration_status()
        for key, value in status.items():
            print(f"  {key}: {value}")
        
        # 测试知识库搜索
        print("\n" + "=" * 60)
        print("知识库搜索测试")
        print("=" * 60)
        
        test_query = "赛博朋克风格"
        print(f"\n查询: {test_query}")
        results = ms.search_knowledge(test_query, top_k=3)
        
        if results:
            for i, result in enumerate(results, 1):
                print(f"  {i}. {result.title} ({result.score:.2%})")
        else:
            print("  未找到结果（可能需要先构建索引）")
        
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        
    except ValueError as e:
        print(f"✗ 错误: {e}")
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        import traceback
        traceback.print_exc()
