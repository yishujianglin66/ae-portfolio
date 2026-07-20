# DaVinci Resolve媒体管理完全指南

> 适用版本：DaVinci Resolve Studio 21.0 | 更新日期：2026-07-13 | 分类：DaVinci Resolve知识库

---

## 目录

- [一、媒体管理基础概念](#一媒体管理基础概念)
- [二、媒体池架构深度解析](#二媒体池架构深度解析)
- [三、媒体导入技术详解](#三媒体导入技术详解)
- [四、媒体组织与文件夹管理](#四媒体组织与文件夹管理)
- [五、元数据管理完全指南](#五元数据管理完全指南)
- [六、媒体缓存与代理系统](#六媒体缓存与代理系统)
- [七、媒体替换与重新链接](#七媒体替换与重新链接)
- [八、媒体管理最佳实践](#八媒体管理最佳实践)
- [九、批量操作与自动化](#九批量操作与自动化)
- [十、故障排查](#十故障排查)
- [十一、性能优化](#十一性能优化)

---

## 一、媒体管理基础概念

### 1.1 媒体管理的重要性

在DaVinci Resolve中，媒体管理是整个工作流程的基础。良好的媒体管理可以：

| 方面 | 影响 |
|------|------|
| **项目稳定性** | 减少媒体离线、崩溃、渲染失败的风险 |
| **工作效率** | 快速定位素材，减少搜索时间 |
| **团队协作** | 确保团队成员使用相同的素材和结构 |
| **版本控制** | 便于管理不同版本的素材 |
| **存储优化** | 合理利用存储空间，避免冗余 |

### 1.2 媒体池核心概念

**媒体池（Media Pool）** 是Resolve中管理所有媒体素材的中央仓库，具有以下特性：

- **层级结构**：根文件夹 → 子文件夹 → 媒体项
- **元数据支持**：支持自定义元数据字段
- **智能分类**：支持智能媒体夹（Smart Bins）
- **批量操作**：支持批量导入、移动、删除
- **代理工作流**：原生支持代理媒体

### 1.3 媒体类型分类

| 媒体类型 | 扩展名 | 说明 |
|---------|--------|------|
| **视频** | .mov, .mp4, .mxf, .avi, .raw | 各种视频格式 |
| **音频** | .wav, .aiff, .mp3, .flac | 各种音频格式 |
| **图像** | .png, .jpg, .exr, .dpx | 静态图像和序列 |
| **RAW格式** | .dng, .arriraw, .red, .cineon | 摄影机RAW文件 |
| **字幕** | .srt, .ass, .xml | 字幕文件 |
| **项目文件** | .drp | Resolve项目文件 |

---

## 二、媒体池架构深度解析

### 2.1 对象模型层次

```python
# Resolve媒体池对象层次结构
# MediaPool
#   ├── GetRootFolder() -> Folder
#   │   ├── GetName() -> str
#   │   ├── GetSubFolders() -> List[Folder]
#   │   ├── AddSubFolder(parent, name) -> Folder
#   │   ├── DeleteSubFolder(folder) -> bool
#   │   └── GetMediaItems() -> List[MediaItem]
#   ├── ImportMedia(folder, filePaths) -> List[MediaItem]
#   ├── ExportMedia(folder, mediaItems, exportOptions) -> bool
#   ├── CreateSmartBin(name, rule) -> Folder
#   └── GetSmartBins() -> List[Folder]

# MediaItem
#   ├── GetName() -> str
#   ├── GetFile() -> str
#   ├── GetClipInfo() -> Dict
#   ├── GetMetadata() -> Dict
#   ├── SetMetadata(metadata) -> bool
#   ├── AddMarker(time, color, note) -> bool
#   ├── GetMarkers() -> List[Dict]
#   ├── SetColorTag(color) -> bool
#   ├── GetColorTag() -> str
#   └── Delete() -> bool
```

### 2.2 媒体池核心方法

```python
import DaVinciResolveScript as bmd
from typing import List, Dict, Optional

class MediaPoolArchitecture:
    """媒体池架构深度解析"""
    
    def __init__(self):
        self.resolve = bmd.scriptapp("Resolve")
        self.project_manager = self.resolve.GetProjectManager()
        self.project = self.project_manager.GetCurrentProject()
        self.media_pool = self.project.GetMediaPool()
    
    def get_root_folder(self):
        """获取根文件夹"""
        return self.media_pool.GetRootFolder()
    
    def create_folder_structure(self, structure: Dict):
        """创建文件夹结构"""
        root = self.get_root_folder()
        
        def create_recursive(parent, items):
            for name, children in items.items():
                folder = self.media_pool.AddSubFolder(parent, name)
                if isinstance(children, dict):
                    create_recursive(folder, children)
        
        create_recursive(root, structure)
    
    def get_folder_by_name(self, folder_name: str, parent=None):
        """按名称查找文件夹"""
        search_root = parent or self.get_root_folder()
        
        # 深度优先搜索
        def search(folder):
            if folder.GetName() == folder_name:
                return folder
            for subfolder in folder.GetSubFolders():
                result = search(subfolder)
                if result:
                    return result
            return None
        
        return search(search_root)
    
    def get_all_media_items(self, folder=None):
        """获取所有媒体项"""
        target_folder = folder or self.get_root_folder()
        items = []
        
        def collect(folder):
            items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(target_folder)
        return items
    
    def count_media_items(self):
        """统计媒体项数量"""
        return len(self.get_all_media_items())
    
    def get_media_item_by_name(self, name: str):
        """按名称查找媒体项"""
        all_items = self.get_all_media_items()
        for item in all_items:
            if item.GetName() == name:
                return item
        return None
```

---

## 三、媒体导入技术详解

### 3.1 基本导入方法

```python
class MediaImporter:
    """媒体导入技术详解"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def import_single_file(self, file_path: str, folder=None) -> object:
        """导入单个文件"""
        target_folder = folder or self.media_pool.GetRootFolder()
        media_items = self.media_pool.ImportMedia(target_folder, [file_path])
        return media_items[0] if media_items else None
    
    def import_multiple_files(self, file_paths: List[str], folder=None) -> List[object]:
        """导入多个文件"""
        target_folder = folder or self.media_pool.GetRootFolder()
        return self.media_pool.ImportMedia(target_folder, file_paths)
    
    def import_folder(self, folder_path: str, recursive: bool = True) -> List[object]:
        """导入文件夹"""
        import os
        
        file_paths = []
        
        def scan_directory(path):
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path) and recursive:
                    scan_directory(full_path)
                else:
                    # 过滤常见媒体文件扩展名
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.mov', '.mp4', '.mxf', '.avi', '.wav', '.aiff', '.png', '.jpg']:
                        file_paths.append(full_path)
        
        scan_directory(folder_path)
        
        return self.media_pool.ImportMedia(
            self.media_pool.GetRootFolder(),
            file_paths
        )
    
    def import_clip_sequence(self, sequence_path: str, folder=None) -> object:
        """导入图像序列"""
        target_folder = folder or self.media_pool.GetRootFolder()
        return self.media_pool.ImportMedia(target_folder, [sequence_path])[0]
    
    def import_from_url(self, url: str, folder=None) -> object:
        """从URL导入（仅支持特定协议）"""
        target_folder = folder or self.media_pool.GetRootFolder()
        return self.media_pool.ImportMedia(target_folder, [url])[0]
    
    def import_proxy_media(self, media_item: object, proxy_path: str) -> bool:
        """导入代理媒体"""
        try:
            media_item.SetProxyFile(proxy_path)
            return True
        except Exception as e:
            print(f"设置代理失败: {e}")
            return False
```

### 3.2 导入选项与配置

```python
class ImportOptions:
    """导入选项配置"""
    
    SUPPORTED_FORMATS = {
        'video': ['.mov', '.mp4', '.mxf', '.avi', '.raw', '.mkv', '.flv'],
        'audio': ['.wav', '.aiff', '.mp3', '.flac', '.ogg'],
        'image': ['.png', '.jpg', '.jpeg', '.tiff', '.exr', '.dpx', '.cin'],
        'raw': ['.dng', '.arriraw', '.red', '.cineon', '.braw', '.gpr'],
        'subtitle': ['.srt', '.ass', '.ssa', '.xml'],
        'project': ['.drp']
    }
    
    def __init__(self):
        self.options = {
            'automaticallyImport': True,
            'createSubfolder': False,
            'subfolderName': '',
            'importAsIndividualClips': True,
            'ignoreDuplicates': False,
            'skipOfflineClips': False,
            'importClipsIntoCurrentTimeline': False,
            'timelineTrackIndex': 1,
            'timelineStartFrame': 0,
            'automaticallySetInOut': False,
            'autoAnalysis': {
                'stabilization': False,
                'sceneCutDetection': False,
                'faceDetection': False,
                'shotTypeDetection': False,
                'colorDetection': False,
                'audioAnalysis': False
            }
        }
    
    def set_auto_analysis(self, options: Dict):
        """设置自动分析选项"""
        for key, value in options.items():
            if key in self.options['autoAnalysis']:
                self.options['autoAnalysis'][key] = value
    
    def enable_all_analysis(self):
        """启用所有自动分析"""
        for key in self.options['autoAnalysis']:
            self.options['autoAnalysis'][key] = True
    
    def disable_all_analysis(self):
        """禁用所有自动分析"""
        for key in self.options['autoAnalysis']:
            self.options['autoAnalysis'][key] = False
    
    def validate_format(self, file_path: str) -> bool:
        """验证文件格式是否支持"""
        ext = os.path.splitext(file_path)[1].lower()
        for formats in self.SUPPORTED_FORMATS.values():
            if ext in formats:
                return True
        return False
    
    def get_format_category(self, file_path: str) -> Optional[str]:
        """获取文件格式类别"""
        ext = os.path.splitext(file_path)[1].lower()
        for category, formats in self.SUPPORTED_FORMATS.items():
            if ext in formats:
                return category
        return None
```

### 3.3 批量导入策略

```python
class BatchImporter:
    """批量导入策略"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def import_with_structure(self, root_path: str):
        """按文件夹结构导入"""
        import os
        
        root_folder = self.media_pool.GetRootFolder()
        
        def import_folder_recursive(source_path, parent_folder):
            folder_name = os.path.basename(source_path)
            resolve_folder = self.media_pool.AddSubFolder(parent_folder, folder_name)
            
            for item in os.listdir(source_path):
                full_path = os.path.join(source_path, item)
                if os.path.isdir(full_path):
                    import_folder_recursive(full_path, resolve_folder)
                else:
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.mov', '.mp4', '.wav', '.png', '.jpg']:
                        self.media_pool.ImportMedia(resolve_folder, [full_path])
        
        import_folder_recursive(root_path, root_folder)
    
    def import_by_format(self, folder_path: str):
        """按格式分类导入"""
        import os
        
        root_folder = self.media_pool.GetRootFolder()
        
        format_folders = {
            'video': None,
            'audio': None,
            'images': None,
            'other': None
        }
        
        # 创建格式分类文件夹
        for name in format_folders:
            format_folders[name] = self.media_pool.AddSubFolder(root_folder, name)
        
        # 导入文件到对应文件夹
        for item in os.listdir(folder_path):
            full_path = os.path.join(folder_path, item)
            if os.path.isfile(full_path):
                ext = os.path.splitext(item)[1].lower()
                
                if ext in ['.mov', '.mp4', '.mxf', '.avi']:
                    target = format_folders['video']
                elif ext in ['.wav', '.aiff', '.mp3']:
                    target = format_folders['audio']
                elif ext in ['.png', '.jpg', '.exr']:
                    target = format_folders['images']
                else:
                    target = format_folders['other']
                
                self.media_pool.ImportMedia(target, [full_path])
    
    def import_with_metadata(self, file_paths: List[str], metadata_list: List[Dict]):
        """导入并设置元数据"""
        root_folder = self.media_pool.GetRootFolder()
        media_items = self.media_pool.ImportMedia(root_folder, file_paths)
        
        for i, item in enumerate(media_items):
            if i < len(metadata_list):
                item.SetMetadata(metadata_list[i])
        
        return media_items
    
    def import_sequence_with_handles(self, sequence_path: str, handles: int = 10):
        """导入带有手柄的序列"""
        import os
        
        file_list = sorted([f for f in os.listdir(sequence_path) 
                          if f.endswith('.dpx') or f.endswith('.exr')])
        
        if not file_list:
            return None
        
        first_frame = file_list[0]
        last_frame = file_list[-1]
        
        # 提取帧号
        import re
        match = re.search(r'(\d+)', first_frame)
        start_frame = int(match.group(1)) if match else 0
        
        full_path = os.path.join(sequence_path, first_frame)
        media_item = self.media_pool.ImportMedia(
            self.media_pool.GetRootFolder(),
            [full_path]
        )[0]
        
        # 设置入点和出点（添加手柄）
        total_frames = len(file_list)
        media_item.SetInPoint(start_frame - handles)
        media_item.SetOutPoint(start_frame + total_frames - 1 + handles)
        
        return media_item
```

---

## 四、媒体组织与文件夹管理

### 4.1 文件夹操作

```python
class FolderManager:
    """文件夹管理"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def create_folder(self, parent_folder, name: str) -> object:
        """创建文件夹"""
        return self.media_pool.AddSubFolder(parent_folder, name)
    
    def delete_folder(self, folder) -> bool:
        """删除文件夹"""
        try:
            folder.Delete()
            return True
        except Exception as e:
            print(f"删除文件夹失败: {e}")
            return False
    
    def rename_folder(self, folder, new_name: str) -> bool:
        """重命名文件夹"""
        try:
            folder.SetName(new_name)
            return True
        except Exception as e:
            print(f"重命名文件夹失败: {e}")
            return False
    
    def move_folder(self, folder, new_parent) -> bool:
        """移动文件夹"""
        try:
            folder.MoveToFolder(new_parent)
            return True
        except Exception as e:
            print(f"移动文件夹失败: {e}")
            return False
    
    def copy_folder(self, folder, new_parent) -> object:
        """复制文件夹"""
        try:
            return folder.CopyToFolder(new_parent)
        except Exception as e:
            print(f"复制文件夹失败: {e}")
            return None
    
    def create_folder_tree(self, structure: List[str]) -> object:
        """创建文件夹树"""
        current = self.media_pool.GetRootFolder()
        
        for name in structure:
            current = self.create_folder(current, name)
        
        return current
    
    def get_folder_hierarchy(self, folder=None) -> Dict:
        """获取文件夹层级结构"""
        target_folder = folder or self.media_pool.GetRootFolder()
        
        def build_tree(f):
            result = {
                'name': f.GetName(),
                'children': []
            }
            
            for subfolder in f.GetSubFolders():
                result['children'].append(build_tree(subfolder))
            
            return result
        
        return build_tree(target_folder)
    
    def count_items_in_folder(self, folder) -> int:
        """统计文件夹中的媒体项数量"""
        return len(folder.GetMediaItems())
    
    def find_empty_folders(self) -> List[object]:
        """查找空文件夹"""
        empty_folders = []
        
        def check_folder(folder):
            if len(folder.GetMediaItems()) == 0 and len(folder.GetSubFolders()) == 0:
                empty_folders.append(folder)
            
            for subfolder in folder.GetSubFolders():
                check_folder(subfolder)
        
        check_folder(self.media_pool.GetRootFolder())
        return empty_folders
    
    def delete_empty_folders(self) -> int:
        """删除所有空文件夹"""
        empty_folders = self.find_empty_folders()
        count = 0
        
        for folder in empty_folders:
            if self.delete_folder(folder):
                count += 1
        
        return count
```

### 4.2 智能媒体夹（Smart Bins）

```python
class SmartBinManager:
    """智能媒体夹管理"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def create_smart_bin(self, name: str, rules: List[Dict]) -> object:
        """创建智能媒体夹"""
        rule_string = self._build_rule_string(rules)
        return self.media_pool.CreateSmartBin(name, rule_string)
    
    def _build_rule_string(self, rules: List[Dict]) -> str:
        """构建规则字符串"""
        rule_parts = []
        
        for rule in rules:
            field = rule.get('field', '')
            operator = rule.get('operator', 'contains')
            value = rule.get('value', '')
            
            rule_parts.append(f"{field} {operator} '{value}'")
        
        return ' AND '.join(rule_parts)
    
    def create_favorite_clips_bin(self) -> object:
        """创建收藏剪辑智能媒体夹"""
        rules = [
            {'field': 'Favorite', 'operator': 'is', 'value': 'true'}
        ]
        return self.create_smart_bin('Favorite Clips', rules)
    
    def create_unused_clips_bin(self) -> object:
        """创建未使用剪辑智能媒体夹"""
        rules = [
            {'field': 'Usage', 'operator': 'is', 'value': 'unused'}
        ]
        return self.create_smart_bin('Unused Clips', rules)
    
    def create_high_frame_rate_bin(self, fps_threshold: int = 60) -> object:
        """创建高帧率剪辑智能媒体夹"""
        rules = [
            {'field': 'Frame Rate', 'operator': '>=', 'value': str(fps_threshold)}
        ]
        return self.create_smart_bin(f'High Frame Rate ({fps_threshold}+)', rules)
    
    def create_long_duration_bin(self, min_duration: float = 60) -> object:
        """创建长时长剪辑智能媒体夹"""
        rules = [
            {'field': 'Duration', 'operator': '>=', 'value': str(min_duration)}
        ]
        return self.create_smart_bin(f'Long Clips ({min_duration}s+)', rules)
    
    def create_by_camera_bin(self, camera_name: str) -> object:
        """按摄像机创建智能媒体夹"""
        rules = [
            {'field': 'Camera', 'operator': 'contains', 'value': camera_name}
        ]
        return self.create_smart_bin(f'Camera - {camera_name}', rules)
    
    def create_by_format_bin(self, format_name: str) -> object:
        """按格式创建智能媒体夹"""
        rules = [
            {'field': 'Format', 'operator': 'contains', 'value': format_name}
        ]
        return self.create_smart_bin(f'Format - {format_name}', rules)
    
    def get_all_smart_bins(self) -> List[object]:
        """获取所有智能媒体夹"""
        return self.media_pool.GetSmartBins()
    
    def update_smart_bin_rules(self, smart_bin, rules: List[Dict]) -> bool:
        """更新智能媒体夹规则"""
        try:
            rule_string = self._build_rule_string(rules)
            smart_bin.SetRules(rule_string)
            return True
        except Exception as e:
            print(f"更新智能媒体夹规则失败: {e}")
            return False
    
    def delete_smart_bin(self, smart_bin) -> bool:
        """删除智能媒体夹"""
        try:
            smart_bin.Delete()
            return True
        except Exception as e:
            print(f"删除智能媒体夹失败: {e}")
            return False
```

---

## 五、元数据管理完全指南

### 5.1 元数据字段详解

```python
class MetadataManager:
    """元数据管理"""
    
    STANDARD_FIELDS = {
        'Basic': [
            'Name', 'Type', 'Format', 'Codec', 'Duration', 'Frame Rate',
            'Resolution', 'Aspect Ratio', 'File Size', 'Date Created',
            'Date Modified', 'File Path', 'Source'
        ],
        'Camera': [
            'Camera', 'Camera Model', 'Lens', 'Focal Length', 'Aperture',
            'ISO', 'Shutter Speed', 'White Balance', 'Exposure', 'Gain'
        ],
        'Audio': [
            'Audio Channels', 'Sample Rate', 'Bit Depth', 'Audio Codec'
        ],
        'Custom': [
            'Shot Name', 'Scene', 'Take', 'Angle', 'Description',
            'Keywords', 'Rating', 'Favorite', 'Color Tag'
        ]
    }
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def get_metadata(self, media_item) -> Dict:
        """获取媒体项元数据"""
        return media_item.GetMetadata()
    
    def set_metadata(self, media_item, metadata: Dict) -> bool:
        """设置媒体项元数据"""
        try:
            media_item.SetMetadata(metadata)
            return True
        except Exception as e:
            print(f"设置元数据失败: {e}")
            return False
    
    def batch_set_metadata(self, media_items: List[object], metadata: Dict) -> int:
        """批量设置元数据"""
        success_count = 0
        
        for item in media_items:
            if self.set_metadata(item, metadata):
                success_count += 1
        
        return success_count
    
    def set_shot_name(self, media_item, shot_name: str) -> bool:
        """设置镜头名称"""
        return self.set_metadata(media_item, {'Shot Name': shot_name})
    
    def set_scene_take(self, media_item, scene: str, take: str) -> bool:
        """设置场景和镜头号"""
        return self.set_metadata(media_item, {
            'Scene': scene,
            'Take': take
        })
    
    def set_rating(self, media_item, rating: int) -> bool:
        """设置评级（1-5星）"""
        if 1 <= rating <= 5:
            return self.set_metadata(media_item, {'Rating': rating})
        return False
    
    def set_favorite(self, media_item, favorite: bool) -> bool:
        """设置收藏标记"""
        return self.set_metadata(media_item, {'Favorite': str(favorite).lower()})
    
    def set_color_tag(self, media_item, color: str) -> bool:
        """设置颜色标签"""
        valid_colors = ['Red', 'Orange', 'Yellow', 'Green', 'Cyan', 'Blue', 'Purple']
        if color in valid_colors:
            return self.set_metadata(media_item, {'Color Tag': color})
        return False
    
    def add_keyword(self, media_item, keyword: str) -> bool:
        """添加关键词"""
        current_meta = self.get_metadata(media_item)
        current_keywords = current_meta.get('Keywords', '')
        
        if current_keywords:
            new_keywords = f"{current_keywords}, {keyword}"
        else:
            new_keywords = keyword
        
        return self.set_metadata(media_item, {'Keywords': new_keywords})
    
    def batch_rename_by_metadata(self, media_items: List[object], pattern: str) -> int:
        """按元数据批量重命名"""
        success_count = 0
        
        for item in media_items:
            meta = self.get_metadata(item)
            
            new_name = pattern
            new_name = new_name.replace('[Scene]', meta.get('Scene', 'Unknown'))
            new_name = new_name.replace('[Take]', meta.get('Take', '01'))
            new_name = new_name.replace('[Shot]', meta.get('Shot Name', 'Shot'))
            new_name = new_name.replace('[Camera]', meta.get('Camera', 'CAM'))
            new_name = new_name.replace('[Date]', meta.get('Date Created', '').replace('-', ''))
            
            try:
                item.SetName(new_name)
                success_count += 1
            except Exception as e:
                print(f"重命名失败: {e}")
        
        return success_count
    
    def export_metadata(self, media_items: List[object], output_path: str) -> bool:
        """导出元数据到CSV"""
        try:
            import csv
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # 写入表头
                headers = ['Name', 'File Path', 'Duration', 'Frame Rate', 
                          'Resolution', 'Scene', 'Take', 'Rating', 'Favorite']
                writer.writerow(headers)
                
                # 写入数据
                for item in media_items:
                    meta = item.GetMetadata()
                    writer.writerow([
                        item.GetName(),
                        item.GetFile(),
                        meta.get('Duration', ''),
                        meta.get('Frame Rate', ''),
                        meta.get('Resolution', ''),
                        meta.get('Scene', ''),
                        meta.get('Take', ''),
                        meta.get('Rating', ''),
                        meta.get('Favorite', '')
                    ])
            
            return True
        except Exception as e:
            print(f"导出元数据失败: {e}")
            return False
    
    def import_metadata(self, csv_path: str) -> int:
        """从CSV导入元数据"""
        try:
            import csv
            
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                success_count = 0
                
                for row in reader:
                    media_item = self._find_media_item_by_name(row.get('Name', ''))
                    
                    if media_item:
                        metadata = {
                            'Scene': row.get('Scene', ''),
                            'Take': row.get('Take', ''),
                            'Rating': row.get('Rating', ''),
                            'Favorite': row.get('Favorite', '')
                        }
                        
                        if self.set_metadata(media_item, metadata):
                            success_count += 1
            
            return success_count
        except Exception as e:
            print(f"导入元数据失败: {e}")
            return 0
    
    def _find_media_item_by_name(self, name: str) -> Optional[object]:
        """按名称查找媒体项"""
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(self.media_pool.GetRootFolder())
        
        for item in all_items:
            if item.GetName() == name:
                return item
        
        return None
```

---

## 六、媒体缓存与代理系统

### 6.1 缓存管理

```python
class CacheManager:
    """媒体缓存管理"""
    
    def __init__(self, resolve):
        self.resolve = resolve
    
    def get_cache_settings(self) -> Dict:
        """获取缓存设置"""
        return {
            'cachePath': self.resolve.GetCachePath(),
            'cacheSize': self.resolve.GetCacheSize(),
            'maxCacheSize': self.resolve.GetMaxCacheSize(),
            'cacheEnabled': self.resolve.GetCacheEnabled()
        }
    
    def set_cache_path(self, path: str) -> bool:
        """设置缓存路径"""
        try:
            self.resolve.SetCachePath(path)
            return True
        except Exception as e:
            print(f"设置缓存路径失败: {e}")
            return False
    
    def set_max_cache_size(self, size_gb: int) -> bool:
        """设置最大缓存大小（GB）"""
        try:
            self.resolve.SetMaxCacheSize(size_gb * 1024 * 1024 * 1024)
            return True
        except Exception as e:
            print(f"设置最大缓存大小失败: {e}")
            return False
    
    def clear_cache(self) -> bool:
        """清除缓存"""
        try:
            self.resolve.ClearCache()
            return True
        except Exception as e:
            print(f"清除缓存失败: {e}")
            return False
    
    def clear_cache_for_project(self, project) -> bool:
        """清除特定项目的缓存"""
        try:
            project.ClearCache()
            return True
        except Exception as e:
            print(f"清除项目缓存失败: {e}")
            return False
    
    def optimize_cache(self) -> bool:
        """优化缓存"""
        try:
            self.resolve.OptimizeCache()
            return True
        except Exception as e:
            print(f"优化缓存失败: {e}")
            return False
    
    def get_cache_usage(self) -> Dict:
        """获取缓存使用情况"""
        return {
            'used': self.resolve.GetCacheSize(),
            'max': self.resolve.GetMaxCacheSize(),
            'percentage': (self.resolve.GetCacheSize() / self.resolve.GetMaxCacheSize()) * 100
        }
    
    def purge_old_cache(self, days: int = 30) -> bool:
        """清除指定天数前的缓存"""
        try:
            self.resolve.PurgeOldCache(days)
            return True
        except Exception as e:
            print(f"清除旧缓存失败: {e}")
            return False
```

### 6.2 代理工作流

```python
class ProxyManager:
    """代理媒体管理"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def create_proxy(self, media_item, proxy_format: str = 'DNxHD') -> bool:
        """为媒体项创建代理"""
        try:
            media_item.GenerateProxy(proxy_format)
            return True
        except Exception as e:
            print(f"生成代理失败: {e}")
            return False
    
    def batch_create_proxies(self, media_items: List[object], 
                            proxy_format: str = 'DNxHD') -> int:
        """批量创建代理"""
        success_count = 0
        
        for item in media_items:
            if self.create_proxy(item, proxy_format):
                success_count += 1
        
        return success_count
    
    def set_proxy_file(self, media_item, proxy_path: str) -> bool:
        """设置代理文件"""
        try:
            media_item.SetProxyFile(proxy_path)
            return True
        except Exception as e:
            print(f"设置代理文件失败: {e}")
            return False
    
    def get_proxy_file(self, media_item) -> Optional[str]:
        """获取代理文件路径"""
        try:
            return media_item.GetProxyFile()
        except Exception as e:
            print(f"获取代理文件失败: {e}")
            return None
    
    def enable_proxy_mode(self, enable: bool) -> bool:
        """启用/禁用代理模式"""
        try:
            self.media_pool.SetProxyMode(enable)
            return True
        except Exception as e:
            print(f"设置代理模式失败: {e}")
            return False
    
    def is_proxy_mode_enabled(self) -> bool:
        """检查代理模式是否启用"""
        try:
            return self.media_pool.GetProxyMode()
        except Exception as e:
            print(f"检查代理模式失败: {e}")
            return False
    
    def relink_proxy(self, media_item, new_proxy_path: str) -> bool:
        """重新链接代理"""
        try:
            media_item.SetProxyFile(new_proxy_path)
            return True
        except Exception as e:
            print(f"重新链接代理失败: {e}")
            return False
    
    def remove_proxy(self, media_item) -> bool:
        """移除代理"""
        try:
            media_item.SetProxyFile('')
            return True
        except Exception as e:
            print(f"移除代理失败: {e}")
            return False
    
    def batch_remove_proxies(self, media_items: List[object]) -> int:
        """批量移除代理"""
        success_count = 0
        
        for item in media_items:
            if self.remove_proxy(item):
                success_count += 1
        
        return success_count
    
    def find_items_without_proxies(self) -> List[object]:
        """查找没有代理的媒体项"""
        items_without_proxy = []
        
        def check_folder(folder):
            for item in folder.GetMediaItems():
                if not item.GetProxyFile():
                    items_without_proxy.append(item)
            
            for subfolder in folder.GetSubFolders():
                check_folder(subfolder)
        
        check_folder(self.media_pool.GetRootFolder())
        return items_without_proxy
    
    def create_proxy_preset(self, name: str, settings: Dict) -> bool:
        """创建代理预设"""
        try:
            self.media_pool.CreateProxyPreset(name, settings)
            return True
        except Exception as e:
            print(f"创建代理预设失败: {e}")
            return False
    
    def get_proxy_presets(self) -> List[str]:
        """获取代理预设列表"""
        try:
            return self.media_pool.GetProxyPresets()
        except Exception as e:
            print(f"获取代理预设失败: {e}")
            return []
```

---

## 七、媒体替换与重新链接

### 7.1 媒体替换

```python
class MediaReplacer:
    """媒体替换"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def replace_media(self, media_item, new_path: str) -> bool:
        """替换媒体文件"""
        try:
            media_item.ReplaceMedia(new_path)
            return True
        except Exception as e:
            print(f"替换媒体失败: {e}")
            return False
    
    def batch_replace_media(self, replacements: Dict[str, str]) -> int:
        """批量替换媒体"""
        success_count = 0
        
        for old_name, new_path in replacements.items():
            media_item = self._find_media_item_by_name(old_name)
            
            if media_item and self.replace_media(media_item, new_path):
                success_count += 1
        
        return success_count
    
    def replace_media_with_sequence(self, media_item, sequence_path: str) -> bool:
        """用序列替换媒体"""
        try:
            media_item.ReplaceMedia(sequence_path)
            return True
        except Exception as e:
            print(f"用序列替换媒体失败: {e}")
            return False
    
    def replace_proxy(self, media_item, new_proxy_path: str) -> bool:
        """替换代理媒体"""
        try:
            media_item.SetProxyFile(new_proxy_path)
            return True
        except Exception as e:
            print(f"替换代理失败: {e}")
            return False
    
    def swap_media(self, item1, item2) -> bool:
        """交换两个媒体项的内容"""
        try:
            path1 = item1.GetFile()
            path2 = item2.GetFile()
            
            item1.ReplaceMedia(path2)
            item2.ReplaceMedia(path1)
            
            return True
        except Exception as e:
            print(f"交换媒体失败: {e}")
            return False
    
    def _find_media_item_by_name(self, name: str) -> Optional[object]:
        """按名称查找媒体项"""
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(self.media_pool.GetRootFolder())
        
        for item in all_items:
            if item.GetName() == name:
                return item
        
        return None
```

### 7.2 重新链接

```python
class RelinkManager:
    """媒体重新链接"""
    
    def __init__(self, project):
        self.project = project
    
    def relink_offline_media(self, search_path: str) -> int:
        """重新链接离线媒体"""
        try:
            offline_count = self.project.GetOfflineMediaCount()
            if offline_count == 0:
                return 0
            
            self.project.RelinkMedia(search_path)
            new_offline_count = self.project.GetOfflineMediaCount()
            
            return offline_count - new_offline_count
        except Exception as e:
            print(f"重新链接媒体失败: {e}")
            return 0
    
    def batch_relink(self, media_items: List[object], new_base_path: str) -> int:
        """批量重新链接"""
        success_count = 0
        
        for item in media_items:
            try:
                old_path = item.GetFile()
                file_name = os.path.basename(old_path)
                new_path = os.path.join(new_base_path, file_name)
                
                if os.path.exists(new_path):
                    item.ReplaceMedia(new_path)
                    success_count += 1
            except Exception as e:
                print(f"重新链接失败: {e}")
        
        return success_count
    
    def find_offline_media(self) -> List[object]:
        """查找离线媒体"""
        try:
            return self.project.GetOfflineMedia()
        except Exception as e:
            print(f"查找离线媒体失败: {e}")
            return []
    
    def count_offline_media(self) -> int:
        """统计离线媒体数量"""
        try:
            return self.project.GetOfflineMediaCount()
        except Exception as e:
            print(f"统计离线媒体失败: {e}")
            return 0
    
    def relink_by_pattern(self, old_pattern: str, new_pattern: str) -> int:
        """按模式重新链接"""
        try:
            offline_media = self.find_offline_media()
            success_count = 0
            
            for item in offline_media:
                old_path = item.GetFile()
                new_path = old_path.replace(old_pattern, new_pattern)
                
                if os.path.exists(new_path):
                    item.ReplaceMedia(new_path)
                    success_count += 1
            
            return success_count
        except Exception as e:
            print(f"按模式重新链接失败: {e}")
            return 0
    
    def consolidate_media(self, media_items: List[object], target_path: str) -> int:
        """整合媒体到统一目录"""
        import shutil
        success_count = 0
        
        for item in media_items:
            try:
                old_path = item.GetFile()
                file_name = os.path.basename(old_path)
                new_path = os.path.join(target_path, file_name)
                
                shutil.copy2(old_path, new_path)
                item.ReplaceMedia(new_path)
                
                success_count += 1
            except Exception as e:
                print(f"整合媒体失败: {e}")
        
        return success_count
```

---

## 八、媒体管理最佳实践

### 8.1 项目文件夹结构模板

```python
class ProjectStructureTemplate:
    """项目文件夹结构模板"""
    
    DEFAULT_STRUCTURE = {
        '01_Footage': {
            '01_A_Roll': {},
            '02_B_Roll': {},
            '03_Interviews': {},
            '04_B-roll': {},
            '05_Archive': {}
        },
        '02_Graphics': {
            '01_Logos': {},
            '02_Titles': {},
            '03_Lower_Thirds': {},
            '04_GFX': {}
        },
        '03_Audio': {
            '01_Dialogue': {},
            '02_Music': {},
            '03_SFX': {},
            '04_Ambience': {}
        },
        '04_Exports': {
            '01_Dailies': {},
            '02_Final': {},
            '03_Preview': {}
        },
        '05_Assets': {
            '01_LUTs': {},
            '02_Presets': {},
            '03_Templates': {}
        }
    }
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def apply_default_structure(self):
        """应用默认文件夹结构"""
        root = self.media_pool.GetRootFolder()
        
        def create_structure(parent, items):
            for name, children in items.items():
                folder = self.media_pool.AddSubFolder(parent, name)
                if isinstance(children, dict):
                    create_structure(folder, children)
        
        create_structure(root, self.DEFAULT_STRUCTURE)
    
    def apply_custom_structure(self, structure: Dict):
        """应用自定义文件夹结构"""
        root = self.media_pool.GetRootFolder()
        
        def create_structure(parent, items):
            for name, children in items.items():
                folder = self.media_pool.AddSubFolder(parent, name)
                if isinstance(children, dict):
                    create_structure(folder, children)
        
        create_structure(root, structure)
    
    def apply_feature_film_structure(self):
        """应用剧情片文件夹结构"""
        structure = {
            'Footage': {
                'Camera_A': {'Scene_01': {}, 'Scene_02': {}, 'Scene_03': {}},
                'Camera_B': {'Scene_01': {}, 'Scene_02': {}, 'Scene_03': {}},
                'Camera_C': {'Scene_01': {}, 'Scene_02': {}, 'Scene_03': {}}
            },
            'Audio': {
                'Production': {'Dialogue': {}, 'SFX': {}, 'Ambience': {}},
                'Post': {'Music': {}, 'ADR': {}, 'Foley': {}}
            },
            'VFX': {'Compositing': {}, 'CGI': {}, 'Motion_Graphics': {}},
            'Color': {'LUTs': {}, 'Reference': {}},
            'Exports': {'Dailies': {}, 'QC': {}, 'Final': {}}
        }
        
        self.apply_custom_structure(structure)
    
    def apply_documentary_structure(self):
        """应用纪录片文件夹结构"""
        structure = {
            'Footage': {
                'Interviews': {'Subject_A': {}, 'Subject_B': {}, 'Subject_C': {}},
                'B-roll': {'Location_01': {}, 'Location_02': {}, 'Location_03': {}},
                'Archive': {'Photos': {}, 'Footage': {}, 'Audio': {}}
            },
            'Audio': {'Dialogue': {}, 'Music': {}, 'SFX': {}, 'Ambience': {}},
            'Graphics': {'Charts': {}, 'Maps': {}, 'Titles': {}},
            'Exports': {'Rough_Cuts': {}, 'Fine_Cuts': {}, 'Final': {}}
        }
        
        self.apply_custom_structure(structure)
    
    def apply_social_media_structure(self):
        """应用社交媒体文件夹结构"""
        structure = {
            'Footage': {'Original': {}, 'Trimmed': {}, 'Graphics': {}},
            'Audio': {'Music': {}, 'SFX': {}, 'Voiceover': {}},
            'Templates': {'Reels': {}, 'TikTok': {}, 'YouTube_Shorts': {}},
            'Exports': {'Draft': {}, 'Final': {}, 'Variants': {}}
        }
        
        self.apply_custom_structure(structure)
```

### 8.2 文件命名规范

```python
class NamingConvention:
    """文件命名规范"""
    
    FEATURE_FILM_PATTERN = "{Scene}_{Shot}_{Take}_{Camera}_{Date}.{ext}"
    DOCUMENTARY_PATTERN = "{Subject}_{Location}_{Date}_{Take}.{ext}"
    COMMERCIAL_PATTERN = "{Client}_{Product}_{Shot}_{Take}.{ext}"
    SOCIAL_MEDIA_PATTERN = "{Platform}_{Content}_{Version}.{ext}"
    
    def format_feature_film(self, scene: str, shot: str, take: str, 
                           camera: str, date: str, ext: str) -> str:
        """格式化剧情片文件名"""
        return self.FEATURE_FILM_PATTERN.format(
            Scene=scene,
            Shot=shot,
            Take=take,
            Camera=camera,
            Date=date,
            ext=ext
        )
    
    def format_documentary(self, subject: str, location: str, 
                          date: str, take: str, ext: str) -> str:
        """格式化纪录片文件名"""
        return self.DOCUMENTARY_PATTERN.format(
            Subject=subject,
            Location=location,
            Date=date,
            Take=take,
            ext=ext
        )
    
    def format_commercial(self, client: str, product: str, 
                         shot: str, take: str, ext: str) -> str:
        """格式化广告文件名"""
        return self.COMMERCIAL_PATTERN.format(
            Client=client,
            Product=product,
            Shot=shot,
            Take=take,
            ext=ext
        )
    
    def format_social_media(self, platform: str, content: str, 
                           version: str, ext: str) -> str:
        """格式化社交媒体文件名"""
        return self.SOCIAL_MEDIA_PATTERN.format(
            Platform=platform,
            Content=content,
            Version=version,
            ext=ext
        )
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        import re
        
        # 移除非法字符
        sanitized = re.sub(r'[\\/:*?"<>|]', '', filename)
        
        # 替换空格和特殊字符
        sanitized = sanitized.replace(' ', '_')
        
        # 限制长度
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255 - len(ext)] + ext
        
        return sanitized
    
    def validate_filename(self, filename: str) -> bool:
        """验证文件名是否符合规范"""
        import re
        
        # 检查非法字符
        if re.search(r'[\\/:*?"<>|]', filename):
            return False
        
        # 检查长度
        if len(filename) > 255:
            return False
        
        # 检查开头和结尾
        if filename.startswith('.') or filename.startswith('_'):
            return False
        
        return True
```

---

## 九、批量操作与自动化

### 9.1 批量选择与操作

```python
class BatchOperations:
    """批量操作"""
    
    def __init__(self, media_pool):
        self.media_pool = media_pool
    
    def select_all_media(self) -> List[object]:
        """选择所有媒体"""
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(self.media_pool.GetRootFolder())
        return all_items
    
    def select_by_format(self, formats: List[str]) -> List[object]:
        """按格式选择媒体"""
        all_items = self.select_all_media()
        return [item for item in all_items 
                if any(item.GetName().lower().endswith(f'.{f.lower()}') for f in formats)]
    
    def select_by_duration(self, min_duration: float = None, 
                          max_duration: float = None) -> List[object]:
        """按时长选择媒体"""
        all_items = self.select_all_media()
        filtered = []
        
        for item in all_items:
            duration = float(item.GetMetadata().get('Duration', 0))
            
            if min_duration and duration < min_duration:
                continue
            if max_duration and duration > max_duration:
                continue
            
            filtered.append(item)
        
        return filtered
    
    def select_by_frame_rate(self, fps: float) -> List[object]:
        """按帧率选择媒体"""
        all_items = self.select_all_media()
        return [item for item in all_items
                if float(item.GetMetadata().get('Frame Rate', 0)) == fps]
    
    def select_by_resolution(self, resolution: str) -> List[object]:
        """按分辨率选择媒体"""
        all_items = self.select_all_media()
        return [item for item in all_items
                if item.GetMetadata().get('Resolution', '') == resolution]
    
    def select_unused_clips(self) -> List[object]:
        """选择未使用的剪辑"""
        all_items = self.select_all_media()
        return [item for item in all_items
                if item.GetMetadata().get('Usage', '') == 'unused']
    
    def batch_delete(self, media_items: List[object]) -> int:
        """批量删除媒体"""
        success_count = 0
        
        for item in media_items:
            try:
                item.Delete()
                success_count += 1
            except Exception as e:
                print(f"删除失败: {e}")
        
        return success_count
    
    def batch_move(self, media_items: List[object], target_folder) -> int:
        """批量移动媒体"""
        success_count = 0
        
        for item in media_items:
            try:
                item.MoveToFolder(target_folder)
                success_count += 1
            except Exception as e:
                print(f"移动失败: {e}")
        
        return success_count
    
    def batch_copy(self, media_items: List[object], target_folder) -> int:
        """批量复制媒体"""
        success_count = 0
        
        for item in media_items:
            try:
                item.CopyToFolder(target_folder)
                success_count += 1
            except Exception as e:
                print(f"复制失败: {e}")
        
        return success_count
    
    def batch_set_color_tag(self, media_items: List[object], color: str) -> int:
        """批量设置颜色标签"""
        valid_colors = ['Red', 'Orange', 'Yellow', 'Green', 'Cyan', 'Blue', 'Purple']
        
        if color not in valid_colors:
            return 0
        
        success_count = 0
        
        for item in media_items:
            try:
                item.SetColorTag(color)
                success_count += 1
            except Exception as e:
                print(f"设置颜色标签失败: {e}")
        
        return success_count
    
    def batch_set_rating(self, media_items: List[object], rating: int) -> int:
        """批量设置评级"""
        if not (1 <= rating <= 5):
            return 0
        
        success_count = 0
        
        for item in media_items:
            try:
                item.SetMetadata({'Rating': rating})
                success_count += 1
            except Exception as e:
                print(f"设置评级失败: {e}")
        
        return success_count
    
    def batch_add_marker(self, media_items: List[object], time: float, 
                        color: str = 'Red', note: str = '') -> int:
        """批量添加标记"""
        success_count = 0
        
        for item in media_items:
            try:
                item.AddMarker(time, color, note)
                success_count += 1
            except Exception as e:
                print(f"添加标记失败: {e}")
        
        return success_count
```

### 9.2 自动化脚本

```python
class MediaAutomation:
    """媒体管理自动化"""
    
    def __init__(self, resolve):
        self.resolve = resolve
        self.project_manager = resolve.GetProjectManager()
        self.project = self.project_manager.GetCurrentProject()
        self.media_pool = self.project.GetMediaPool()
    
    def auto_organize_imported_media(self):
        """自动整理导入的媒体"""
        all_items = self._get_all_media_items()
        
        # 按格式分类
        format_folders = {
            'video': None,
            'audio': None,
            'images': None,
            'other': None
        }
        
        root = self.media_pool.GetRootFolder()
        
        # 创建或获取格式文件夹
        for name in format_folders:
            existing = self._find_folder_by_name(name, root)
            format_folders[name] = existing or self.media_pool.AddSubFolder(root, name)
        
        # 移动媒体到对应文件夹
        for item in all_items:
            ext = os.path.splitext(item.GetName())[1].lower()
            
            if ext in ['.mov', '.mp4', '.mxf', '.avi']:
                target = format_folders['video']
            elif ext in ['.wav', '.aiff', '.mp3']:
                target = format_folders['audio']
            elif ext in ['.png', '.jpg', '.exr']:
                target = format_folders['images']
            else:
                target = format_folders['other']
            
            item.MoveToFolder(target)
    
    def auto_analyze_media(self):
        """自动分析媒体"""
        all_items = self._get_all_media_items()
        
        for item in all_items:
            try:
                # 场景检测
                item.AnalyzeSceneCuts()
                
                # 人脸检测
                item.AnalyzeFaces()
                
                # 颜色检测
                item.AnalyzeColor()
            except Exception as e:
                print(f"分析媒体失败: {item.GetName()} - {e}")
    
    def auto_create_proxies(self, format: str = 'DNxHD'):
        """自动创建代理"""
        items_without_proxy = self._find_items_without_proxies()
        
        for item in items_without_proxy:
            try:
                item.GenerateProxy(format)
            except Exception as e:
                print(f"创建代理失败: {item.GetName()} - {e}")
    
    def auto_cleanup_unused_media(self):
        """自动清理未使用的媒体"""
        unused_items = self._find_unused_items()
        
        for item in unused_items:
            try:
                item.Delete()
            except Exception as e:
                print(f"删除未使用媒体失败: {item.GetName()} - {e}")
    
    def auto_export_dailies(self, output_path: str):
        """自动导出日报"""
        all_items = self._get_all_media_items()
        daily_items = [item for item in all_items 
                       if self._is_today(item)]
        
        # 创建日报文件夹
        import datetime
        today = datetime.date.today().strftime('%Y%m%d')
        daily_folder = os.path.join(output_path, f'Dailies_{today}')
        
        if not os.path.exists(daily_folder):
            os.makedirs(daily_folder)
        
        # 导出媒体信息
        import csv
        csv_path = os.path.join(daily_folder, 'dailies_report.csv')
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Duration', 'Frame Rate', 'Resolution', 'Status'])
            
            for item in daily_items:
                meta = item.GetMetadata()
                writer.writerow([
                    item.GetName(),
                    meta.get('Duration', ''),
                    meta.get('Frame Rate', ''),
                    meta.get('Resolution', ''),
                    'OK'
                ])
    
    def _get_all_media_items(self):
        """获取所有媒体项"""
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(self.media_pool.GetRootFolder())
        return all_items
    
    def _find_folder_by_name(self, name: str, parent=None):
        """按名称查找文件夹"""
        search_root = parent or self.media_pool.GetRootFolder()
        
        def search(folder):
            if folder.GetName() == name:
                return folder
            for subfolder in folder.GetSubFolders():
                result = search(subfolder)
                if result:
                    return result
            return None
        
        return search(search_root)
    
    def _find_items_without_proxies(self):
        """查找没有代理的媒体项"""
        return [item for item in self._get_all_media_items() 
                if not item.GetProxyFile()]
    
    def _find_unused_items(self):
        """查找未使用的媒体项"""
        return [item for item in self._get_all_media_items()
                if item.GetMetadata().get('Usage', '') == 'unused']
    
    def _is_today(self, media_item):
        """检查媒体项是否是今天导入的"""
        import datetime
        
        created_date = media_item.GetMetadata().get('Date Created', '')
        if not created_date:
            return False
        
        today = datetime.date.today().strftime('%Y-%m-%d')
        return created_date.startswith(today)
```

---

## 十、故障排查

### 10.1 常见问题与解决方案

```python
class MediaTroubleshooter:
    """媒体管理故障排查"""
    
    COMMON_ISSUES = {
        'offline_media': {
            'description': '媒体显示为离线状态',
            'causes': ['文件被移动或重命名', '存储设备未连接', '网络路径断开'],
            'solutions': [
                '使用重新链接功能查找媒体',
                '检查存储设备连接状态',
                '确认网络路径可访问',
                '使用批量重新链接功能'
            ]
        },
        'proxy_not_found': {
            'description': '代理媒体无法找到',
            'causes': ['代理文件被删除', '代理路径已更改', '代理生成失败'],
            'solutions': [
                '重新生成代理媒体',
                '检查代理文件路径',
                '重新链接代理文件'
            ]
        },
        'import_failure': {
            'description': '媒体导入失败',
            'causes': ['格式不支持', '文件损坏', '权限不足', '磁盘空间不足'],
            'solutions': [
                '确认文件格式兼容性',
                '检查文件完整性',
                '确保有文件读写权限',
                '检查磁盘剩余空间'
            ]
        },
        'cache_full': {
            'description': '媒体缓存已满',
            'causes': ['缓存空间不足', '缓存路径不可写', '长时间未清理'],
            'solutions': [
                '扩大缓存空间',
                '清理旧缓存',
                '更改缓存路径',
                '优化缓存设置'
            ]
        },
        'slow_import': {
            'description': '媒体导入速度缓慢',
            'causes': ['网络存储', '文件过大', '自动分析开启', '磁盘速度慢'],
            'solutions': [
                '关闭自动分析',
                '使用本地存储',
                '分批导入',
                '使用高速存储设备'
            ]
        },
        'metadata_lost': {
            'description': '元数据丢失',
            'causes': ['文件重新链接', '格式转换', '元数据字段不支持'],
            'solutions': [
                '备份元数据到CSV',
                '使用支持元数据的格式',
                '手动重新输入元数据'
            ]
        }
    }
    
    def __init__(self, project):
        self.project = project
    
    def diagnose_offline_media(self) -> Dict:
        """诊断离线媒体问题"""
        offline_count = self.project.GetOfflineMediaCount()
        
        if offline_count == 0:
            return {'status': 'ok', 'message': '没有离线媒体'}
        
        return {
            'status': 'error',
            'offline_count': offline_count,
            'message': f'发现 {offline_count} 个离线媒体项',
            'suggestion': '使用重新链接功能或检查存储设备'
        }
    
    def diagnose_cache_issues(self) -> Dict:
        """诊断缓存问题"""
        resolve = self.project.GetResolve()
        cache_usage = resolve.GetCacheSize()
        max_cache = resolve.GetMaxCacheSize()
        
        percentage = (cache_usage / max_cache) * 100
        
        if percentage > 90:
            return {
                'status': 'warning',
                'cache_usage_percentage': percentage,
                'message': '缓存空间即将用尽',
                'suggestion': '清理旧缓存或扩大缓存空间'
            }
        
        return {
            'status': 'ok',
            'cache_usage_percentage': percentage,
            'message': '缓存空间充足'
        }
    
    def diagnose_proxy_issues(self) -> Dict:
        """诊断代理问题"""
        media_pool = self.project.GetMediaPool()
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(media_pool.GetRootFolder())
        
        items_without_proxy = [item for item in all_items 
                              if not item.GetProxyFile()]
        
        if len(items_without_proxy) > 0:
            return {
                'status': 'warning',
                'items_without_proxy': len(items_without_proxy),
                'message': f'{len(items_without_proxy)} 个媒体项没有代理',
                'suggestion': '批量创建代理媒体'
            }
        
        return {
            'status': 'ok',
            'message': '所有媒体项都有代理'
        }
    
    def run_full_diagnostic(self) -> Dict:
        """运行完整诊断"""
        return {
            'offline_media': self.diagnose_offline_media(),
            'cache': self.diagnose_cache_issues(),
            'proxy': self.diagnose_proxy_issues()
        }
    
    def fix_offline_media(self, search_path: str) -> int:
        """修复离线媒体"""
        return self.project.RelinkMedia(search_path)
    
    def fix_cache_issues(self) -> bool:
        """修复缓存问题"""
        resolve = self.project.GetResolve()
        resolve.ClearCache()
        return True
    
    def fix_proxy_issues(self, format: str = 'DNxHD') -> int:
        """修复代理问题"""
        media_pool = self.project.GetMediaPool()
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(media_pool.GetRootFolder())
        
        items_without_proxy = [item for item in all_items 
                              if not item.GetProxyFile()]
        
        success_count = 0
        for item in items_without_proxy:
            try:
                item.GenerateProxy(format)
                success_count += 1
            except:
                pass
        
        return success_count
```

---

## 十一、性能优化

### 11.1 导入性能优化

```python
class PerformanceOptimizer:
    """媒体管理性能优化"""
    
    def __init__(self, resolve):
        self.resolve = resolve
        self.project_manager = resolve.GetProjectManager()
        self.project = self.project_manager.GetCurrentProject()
        self.media_pool = self.project.GetMediaPool()
    
    def optimize_import_speed(self):
        """优化导入速度"""
        # 关闭自动分析
        self.project.SetAutoAnalysisEnabled(False)
        
        # 设置导入选项
        import_options = {
            'automaticallySetInOut': False,
            'autoAnalysis': {
                'stabilization': False,
                'sceneCutDetection': False,
                'faceDetection': False,
                'shotTypeDetection': False,
                'colorDetection': False,
                'audioAnalysis': False
            }
        }
        
        return import_options
    
    def optimize_cache_performance(self):
        """优化缓存性能"""
        # 设置合理的缓存大小
        self.resolve.SetMaxCacheSize(50 * 1024 * 1024 * 1024)  # 50GB
        
        # 优化缓存路径到高速存储
        import os
        cache_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'ResolveCache')
        
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        
        self.resolve.SetCachePath(cache_path)
    
    def optimize_proxy_workflow(self):
        """优化代理工作流"""
        # 使用高效的代理格式
        proxy_settings = {
            'format': 'DNxHD',
            'resolution': 'Half',
            'codec': 'DNxHD 145'
        }
        
        return proxy_settings
    
    def optimize_disk_access(self):
        """优化磁盘访问"""
        # 使用本地高速存储
        # SSD优于HDD，本地优于网络
        
        return {
            'recommendation': '使用SSD存储媒体文件',
            'avoid': '避免使用网络存储进行实时编辑'
        }
    
    def optimize_project_size(self):
        """优化项目大小"""
        # 清理未使用的媒体
        unused_items = self._find_unused_items()
        
        for item in unused_items:
            try:
                item.Delete()
            except:
                pass
        
        # 清理空文件夹
        empty_folders = self._find_empty_folders()
        
        for folder in empty_folders:
            try:
                folder.Delete()
            except:
                pass
    
    def _find_unused_items(self):
        """查找未使用的媒体项"""
        all_items = []
        
        def collect(folder):
            all_items.extend(folder.GetMediaItems())
            for subfolder in folder.GetSubFolders():
                collect(subfolder)
        
        collect(self.media_pool.GetRootFolder())
        
        return [item for item in all_items
                if item.GetMetadata().get('Usage', '') == 'unused']
    
    def _find_empty_folders(self):
        """查找空文件夹"""
        empty_folders = []
        
        def check_folder(folder):
            if len(folder.GetMediaItems()) == 0 and len(folder.GetSubFolders()) == 0:
                empty_folders.append(folder)
            
            for subfolder in folder.GetSubFolders():
                check_folder(subfolder)
        
        check_folder(self.media_pool.GetRootFolder())
        return empty_folders
```

---

*本指南涵盖 DaVinci Resolve 媒体管理的完整知识体系，包括媒体池架构、导入技术、文件夹管理、元数据系统、缓存代理、批量操作、故障排查与性能优化等核心模块*
