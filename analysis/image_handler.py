#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图片处理模块 - 自动保存用户上传的图片

功能：
1. 监控附件目录，自动发现新上传的图片
2. 根据上下文智能分类保存图片
3. 支持批量处理和重命名
4. 自动更新日记中的图片引用

使用方式：
    from image_handler import ImageHandler
    
    handler = ImageHandler()
    
    # 扫描并保存所有新图片
    handler.scan_and_save()
    
    # 手动保存指定图片
    handler.save_image(source_path, target_name, category='daily')
"""

import os
import shutil
import glob
from datetime import datetime
from pathlib import Path


class ImageHandler:
    """图片处理器"""
    
    # 附件目录（Trae上传的图片会存放在这里）
    ATTACHMENTS_DIR = Path(os.path.expanduser("~/.trae-cn/attachments"))
    
    # 目标目录配置
    TARGET_DIRS = {
        'daily': '01-日常记录',           # 日常记录图片
        'team': '06-部门人员资料',         # 部门人员资料图片
        'knowledge': '05-知识补充',        # 知识补充图片
        'report': '02-月度报告',           # 月度报告图片
        'training': '06-部门人员资料',     # 培训资料图片
    }
    
    def __init__(self, base_dir: str = None):
        self.base_dir = Path(base_dir) if base_dir else \
            Path(__file__).parent / "14-职场学习成长档案"
        
        # 确保所有目标目录存在
        for dir_name in self.TARGET_DIRS.values():
            (self.base_dir / dir_name).mkdir(parents=True, exist_ok=True)
    
    def scan_attachments(self) -> list:
        """扫描附件目录，返回所有图片文件"""
        images = []
        
        if self.ATTACHMENTS_DIR.exists():
            for subdir in self.ATTACHMENTS_DIR.iterdir():
                if subdir.is_dir():
                    for file in subdir.glob('*.jpg'):
                        images.append(str(file))
                    for file in subdir.glob('*.png'):
                        images.append(str(file))
                    for file in subdir.glob('*.jpeg'):
                        images.append(str(file))
        
        return images
    
    def save_image(self, source_path: str, target_name: str, 
                   category: str = 'daily', date: str = None) -> str:
        """保存图片到指定目录
        
        Args:
            source_path: 源文件路径
            target_name: 目标文件名（不含扩展名）
            category: 分类（daily/team/knowledge/report/training）
            date: 日期（用于日常记录分类）
            
        Returns:
            保存后的文件路径
        """
        # 获取扩展名
        ext = Path(source_path).suffix.lower()
        
        # 构建目标路径
        target_dir = self.base_dir / self.TARGET_DIRS.get(category, '01-日常记录')
        
        # 如果是日常记录，按日期分类
        if category == 'daily' and date:
            target_dir = target_dir / date[:7]  # YYYY-MM
            target_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建目标文件名
        target_filename = f"{target_name}{ext}"
        target_path = target_dir / target_filename
        
        # 复制文件
        shutil.copy2(source_path, target_path)
        
        # 返回相对路径（用于Markdown引用）
        return str(target_path.relative_to(self.base_dir))
    
    def scan_and_save(self, category: str = 'daily', date: str = None) -> list:
        """扫描附件目录并保存所有新图片
        
        Args:
            category: 默认分类
            date: 日期
            
        Returns:
            保存的文件路径列表
        """
        images = self.scan_attachments()
        saved_paths = []
        
        for i, image_path in enumerate(images, 1):
            # 使用时间戳作为文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_name = f"{timestamp}_{i}"
            
            try:
                saved_path = self.save_image(image_path, target_name, category, date)
                saved_paths.append(saved_path)
                print(f"已保存: {saved_path}")
            except Exception as e:
                print(f"保存失败 {image_path}: {e}")
        
        return saved_paths
    
    def list_saved_images(self, category: str = None) -> list:
        """列出已保存的图片
        
        Args:
            category: 分类筛选
            
        Returns:
            图片路径列表
        """
        images = []
        
        if category:
            target_dir = self.base_dir / self.TARGET_DIRS.get(category, '')
            if target_dir.exists():
                for file in target_dir.rglob('*.jpg'):
                    images.append(str(file.relative_to(self.base_dir)))
                for file in target_dir.rglob('*.png'):
                    images.append(str(file.relative_to(self.base_dir)))
        else:
            # 搜索所有分类
            for dir_name in self.TARGET_DIRS.values():
                target_dir = self.base_dir / dir_name
                if target_dir.exists():
                    for file in target_dir.rglob('*.jpg'):
                        images.append(str(file.relative_to(self.base_dir)))
                    for file in target_dir.rglob('*.png'):
                        images.append(str(file.relative_to(self.base_dir)))
        
        return sorted(images)
    
    def create_markdown_link(self, relative_path: str, alt_text: str = '') -> str:
        """创建Markdown图片链接
        
        Args:
            relative_path: 相对路径
            alt_text: 图片描述
            
        Returns:
            Markdown图片链接
        """
        return f"![{alt_text}]({relative_path})"


# 全局实例
_handler = None


def get_handler() -> ImageHandler:
    """获取全局处理器实例"""
    global _handler
    if _handler is None:
        _handler = ImageHandler()
    return _handler


def save_images(category: str = 'daily', date: str = None) -> list:
    """快捷函数：扫描并保存图片"""
    return get_handler().scan_and_save(category, date)


def list_images(category: str = None) -> list:
    """快捷函数：列出已保存图片"""
    return get_handler().list_saved_images(category)


if __name__ == "__main__":
    handler = ImageHandler()
    
    print("=" * 60)
    print("图片处理模块 - 测试")
    print("=" * 60)
    
    # 扫描附件
    attachments = handler.scan_attachments()
    print(f"\n发现附件图片: {len(attachments)} 张")
    for img in attachments:
        print(f"  - {img}")
    
    # 列出已保存图片
    saved = handler.list_saved_images()
    print(f"\n已保存图片: {len(saved)} 张")
    for img in saved[:5]:
        print(f"  - {img}")
    
    # 测试保存
    if attachments:
        print(f"\n测试保存第一张图片...")
        try:
            result = handler.save_image(
                attachments[0], 
                "测试图片", 
                category='team',
                date=datetime.now().strftime("%Y-%m-%d")
            )
            print(f"保存成功: {result}")
        except Exception as e:
            print(f"保存失败: {e}")
    
    print("\n" + "=" * 60)
    print("测试完成")