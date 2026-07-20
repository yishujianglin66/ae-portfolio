#!/usr/bin/env python3
"""
创建资源库缺失的目录结构
补全 AE 项目资源库骨架
"""
from __future__ import annotations

from pathlib import Path

RES_ROOT = Path("D:/AE-Work/resources")

# 需要创建的目录结构
DIRECTORY_STRUCTURE = {
    "plugins": [
        "ZXP安装包",
        "第三方插件",
        "Red Giant",
        "Boris FX",
        "Video Copilot",
        "Aescripts",
        "中文汉化插件",
    ],
    "scripts": [
        "ScriptUI Panels",
        "表达式脚本",
        "工具脚本",
        "动画脚本",
        "调色脚本",
        "3D脚本",
        "文字动画脚本",
        "中文汉化脚本",
    ],
    "presets": [
        "调色预设",
        "转场预设",
        "文字动画预设",
        "粒子预设",
        "特效预设",
        "动效预设",
        "UI动画预设",
    ],
    "effects": [
        "overlays",
        "序列帧贴图",
        "光点类",
        "刀光类",
        "图案类",
        "扩散旋转类",
        "扭曲烟雾类",
        "文字类",
        "无缝贴图类",
        "溅射光点类",
        "物件特效贴图",
        "物体类",
        "魔法阵类",
        "3D模型",
        "UV动画类",
    ],
    "videos": [
        "实拍素材",
        "转场视频",
        "特效视频",
        "背景视频",
        "漏光光效",
        "故障干扰",
        "胶片颗粒",
        "4K素材",
        "绿幕素材",
    ],
    "images": [
        "背景图",
        "纹理贴图",
        "PNG免抠",
        "PSD分层",
        "图标素材",
        "参考图",
        "分镜素材",
    ],
    "templates": [
        "片头模板",
        "片尾模板",
        "字幕模板",
        "转场模板",
        "商业模板",
        "MG动画模板",
        "抖音快手模板",
        "婚礼模板",
        "企业宣传模板",
    ],
    "software": [
        "AE插件安装包",
        "PR插件安装包",
        "达芬奇插件",
        "其他软件",
    ],
    "audio": [
        "music",
        "soundfx",
        "whoosh",
        "转场音效",
        "环境音效",
    ],
}


def main() -> None:
    print("=== 创建资源库目录结构 ===\n")
    created_count = 0
    existed_count = 0

    for top_dir, sub_dirs in DIRECTORY_STRUCTURE.items():
        top_path = RES_ROOT / top_dir
        if not top_path.exists():
            top_path.mkdir(parents=True, exist_ok=True)
            print(f"  创建目录: {top_dir}")
            created_count += 1
        else:
            print(f"  已存在: {top_dir}")
            existed_count += 1

        for sub_dir in sub_dirs:
            sub_path = top_path / sub_dir
            if not sub_path.exists():
                sub_path.mkdir(parents=True, exist_ok=True)
                print(f"    创建子目录: {sub_dir}")
                created_count += 1
            else:
                existed_count += 1

    # 创建 README 占位文件说明用途
    for top_dir in DIRECTORY_STRUCTURE.keys():
        readme = RES_ROOT / top_dir / "README.txt"
        if not readme.exists():
            readme.write_text(
                f"{top_dir} 资源目录\n"
                f"存放 AE 项目所需的 {top_dir} 类资源\n"
                f"由资源索引服务统一管理\n",
                encoding="utf-8",
            )

    print(f"\n=== 完成 ===")
    print(f"  新建目录: {created_count} 个")
    print(f"  已存在目录: {existed_count} 个")
    print(f"  资源库根目录: {RES_ROOT}")


if __name__ == "__main__":
    main()
