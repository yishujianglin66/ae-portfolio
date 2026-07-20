# DaVinci Resolve Media页面完全指南

> 适用版本：DaVinci Resolve Studio 21.0 | 更新日期：2026-07-14 | 分类：DaVinci Resolve知识库

---

## 目录

- [一、Media页面核心概念](#一media页面核心概念)
- [二、媒体池架构](#二媒体池架构)
- [三、素材导入技术](#三素材导入技术)
- [四、媒体管理工具](#四媒体管理工具)
- [五、代理工作流](#五代理工作流)
- [六、媒体组织策略](#六媒体组织策略)
- [七、批量媒体操作](#七批量媒体操作)
- [八、Media页面API自动化](#八media页面api自动化)
- [九、故障排查](#九故障排查)
- [十、性能优化](#十性能优化)

---

## 一、Media页面核心概念

### 1.1 Media页面定位

Media页面是DaVinci Resolve中专门为媒体管理设计的工作区，具有以下特点：

| 特性 | 说明 |
|------|------|
| **媒体池管理** | 集中管理所有项目素材 |
| **素材导入** | 支持多种格式和导入方式 |
| **元数据管理** | 完整的元数据编辑和搜索 |
| **代理工作流** | 原生支持代理媒体 |
| **媒体组织** | 文件夹结构和标记系统 |
| **批量操作** | 高效的批量处理能力 |

### 1.2 界面布局

```python
# Media页面界面布局
# ┌─────────────────────────────────────────────────────────┐
# │ 工具栏 (Toolbar)                                       │
# │ 导入/组织/搜索/预览工具                                │
# ├─────────────────────────────────────────────────────────┤
# │ 媒体池面板 (Media Pool)    │ 预览面板 (Preview)        │
# │ 文件夹结构/素材列表         │ 视频预览/元数据信息        │
# ├───────────────────────────┼─────────────────────────────┤
# │ 元数据面板 (Metadata)      │ 缩略图视图/列表视图切换    │
# │ 素材属性/关键词/标记        │                            │
# └───────────────────────────┴─────────────────────────────┘
```

### 1.3 核心快捷键

```python
class MediaPageShortcuts:
    """Media页面核心快捷键"""
    
    NAVIGATION = {
        "Space": "播放/暂停",
        "J/K/L": "倒放/暂停/正放",
        "F": "帧精确模式",
        "H": "适合视图",
        "Z": "缩放工具",
        "Shift+Z": "重置缩放",
        "1": "缩略图视图",
        "2": "列表视图",
        "3": "元数据视图"
    }
    
    IMPORT_EXPORT = {
        "Ctrl+I": "导入媒体",
        "Ctrl+Shift+I": "导入文件夹",
        "Ctrl+E": "导出媒体",
        "Ctrl+D": "复制素材",
        "Delete": "删除素材"
    }
    
    ORGANIZATION = {
        "Ctrl+N": "新建文件夹",
        "Ctrl+G": "创建智能文件夹",
        "F2": "重命名",
        "Ctrl+Shift+M": "添加标记",
        "Ctrl+F": "搜索",
        "Ctrl+A": "全选"
    }
```

---

## 二、媒体池架构

### 2.1 媒体池层次结构

```python
class MediaPoolStructure:
    """媒体池层次结构"""
    
    ROOT_LEVEL = [
        "Root Folder",      # 根文件夹
        "Media Storage",    # 媒体存储
        "Favorites",        # 收藏夹
        "Smart Bins"        # 智能文件夹
    ]
    
    SUBFOLDER_TYPES = [
        "Footage",          # 视频素材
        "Audio",            # 音频素材
        "Images",           # 图片素材
        "Graphics",         # 图形素材
        "Projects",         # 项目文件
        "Exports"           # 导出文件
    ]
    
    MEDIA_ITEM_TYPES = [
        "Video",            # 视频
        "Audio",            # 音频
        "Still",            # 静帧
        "Sequence",         # 序列
        "Timeline",         # 时间线
        "MultiCam"          # 多机位
    ]
```

### 2.2 媒体池管理器

```python
class MediaPoolManager:
    """媒体池管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
        self.root_folder = None
    
    def get_media_pool(self):
        """获取媒体池"""
        try:
            project = self.engine.get_project()
            self.media_pool = project.GetMediaPool()
            return self.media_pool
        except Exception as e:
            print(f"获取媒体池失败: {e}")
            return None
    
    def get_root_folder(self):
        """获取根文件夹"""
        try:
            if not self.media_pool:
                self.get_media_pool()
            
            self.root_folder = self.media_pool.GetRootFolder()
            return self.root_folder
        except Exception as e:
            print(f"获取根文件夹失败: {e}")
            return None
    
    def create_folder(self, parent_folder, name):
        """创建文件夹"""
        try:
            return self.media_pool.AddSubFolder(parent_folder, name)
        except Exception as e:
            print(f"创建文件夹失败 {name}: {e}")
            return None
    
    def delete_folder(self, folder):
        """删除文件夹"""
        try:
            return self.media_pool.DeleteFolder(folder)
        except Exception as e:
            print(f"删除文件夹失败: {e}")
            return False
    
    def rename_folder(self, folder, new_name):
        """重命名文件夹"""
        try:
            return folder.SetName(new_name)
        except Exception as e:
            print(f"重命名文件夹失败: {e}")
            return False
    
    def get_folder_by_name(self, name, parent_folder=None):
        """按名称查找文件夹"""
        try:
            search_folder = parent_folder or self.get_root_folder()
            
            for subfolder in search_folder.GetSubFolderList():
                if subfolder.GetName() == name:
                    return subfolder
            
            return None
        except Exception as e:
            print(f"查找文件夹失败: {e}")
            return None
    
    def get_all_folders(self, folder=None):
        """获取所有文件夹"""
        try:
            results = []
            current_folder = folder or self.get_root_folder()
            
            results.append(current_folder)
            
            for subfolder in current_folder.GetSubFolderList():
                results.extend(self.get_all_folders(subfolder))
            
            return results
        except Exception as e:
            print(f"获取文件夹列表失败: {e}")
            return []
```

---

## 三、素材导入技术

### 3.1 基础导入方法

```python
class MediaImporter:
    """媒体导入器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def import_files(self, file_paths, target_folder=None):
        """导入文件"""
        try:
            target = target_folder or self.media_pool.GetRootFolder()
            return self.media_pool.ImportMedia(target, file_paths)
        except Exception as e:
            print(f"导入文件失败: {e}")
            return []
    
    def import_folder(self, folder_path, target_folder=None):
        """导入文件夹"""
        try:
            import os
            
            file_paths = []
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if self._is_supported_format(f):
                        file_paths.append(os.path.join(root, f))
            
            if not file_paths:
                return []
            
            target = target_folder or self.media_pool.GetRootFolder()
            return self.media_pool.ImportMedia(target, file_paths)
        except Exception as e:
            print(f"导入文件夹失败: {e}")
            return []
    
    def import_media_storage(self, storage_path):
        """导入媒体存储"""
        try:
            return self.media_pool.ImportMediaStorage(storage_path)
        except Exception as e:
            print(f"导入媒体存储失败: {e}")
            return False
    
    def _is_supported_format(self, filename):
        """检查是否为支持的格式"""
        supported_extensions = [
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm',
            '.mp3', '.wav', '.aiff', '.flac', '.m4a',
            '.jpg', '.jpeg', '.png', '.tiff', '.exr', '.dpx', '.cin'
        ]
        return any(filename.lower().endswith(ext) for ext in supported_extensions)
    
    def import_sequence(self, sequence_path, target_folder=None):
        """导入图像序列"""
        try:
            target = target_folder or self.media_pool.GetRootFolder()
            return self.media_pool.ImportMedia(target, [sequence_path], True)
        except Exception as e:
            print(f"导入序列失败: {e}")
            return []
    
    def import_proxy(self, proxy_paths, target_folder=None):
        """导入代理媒体"""
        try:
            target = target_folder or self.media_pool.GetRootFolder()
            return self.media_pool.ImportProxyMedia(target, proxy_paths)
        except Exception as e:
            print(f"导入代理失败: {e}")
            return []
```

### 3.2 导入配置与选项

```python
class ImportOptions:
    """导入选项配置"""
    
    def __init__(self):
        self.options = {
            "CopyToMediaPool": False,
            "AutoImport": False,
            "CreateSubfolders": True,
            "ImportAsSingleClip": False,
            "IgnoreDuplicates": True,
            "UseFolderNames": True,
            "TranscodeOnImport": False,
            "TranscodeFormat": "DNxHR HQ",
            "ProxyMode": "Off",
            "ProxyResolution": "1920x1080"
        }
    
    def set_copy_to_pool(self, enable=True):
        """设置复制到媒体池"""
        self.options["CopyToMediaPool"] = enable
    
    def set_auto_import(self, enable=True):
        """设置自动导入"""
        self.options["AutoImport"] = enable
    
    def set_create_subfolders(self, enable=True):
        """设置创建子文件夹"""
        self.options["CreateSubfolders"] = enable
    
    def set_transcode_on_import(self, enable=True, format="DNxHR HQ"):
        """设置导入时转码"""
        self.options["TranscodeOnImport"] = enable
        self.options["TranscodeFormat"] = format
    
    def set_proxy_mode(self, mode="Off", resolution="1920x1080"):
        """设置代理模式"""
        self.options["ProxyMode"] = mode
        self.options["ProxyResolution"] = resolution
    
    def get_options(self):
        """获取选项"""
        return self.options
```

---

## 四、媒体管理工具

### 4.1 元数据管理

```python
class MetadataManager:
    """元数据管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def get_metadata(self, media_item):
        """获取元数据"""
        try:
            return media_item.GetMetadata()
        except Exception as e:
            print(f"获取元数据失败: {e}")
            return {}
    
    def set_metadata(self, media_item, metadata):
        """设置元数据"""
        try:
            return media_item.SetMetadata(metadata)
        except Exception as e:
            print(f"设置元数据失败: {e}")
            return False
    
    def set_keyword(self, media_item, keyword):
        """设置关键词"""
        try:
            return media_item.SetKeyword(keyword)
        except Exception as e:
            print(f"设置关键词失败: {e}")
            return False
    
    def add_keyword(self, media_item, keyword):
        """添加关键词"""
        try:
            keywords = self.get_keywords(media_item)
            if keyword not in keywords:
                keywords.append(keyword)
                return media_item.SetKeywords(keywords)
            return True
        except Exception as e:
            print(f"添加关键词失败: {e}")
            return False
    
    def get_keywords(self, media_item):
        """获取关键词列表"""
        try:
            return media_item.GetKeywords()
        except Exception as e:
            print(f"获取关键词失败: {e}")
            return []
    
    def remove_keyword(self, media_item, keyword):
        """移除关键词"""
        try:
            keywords = self.get_keywords(media_item)
            if keyword in keywords:
                keywords.remove(keyword)
                return media_item.SetKeywords(keywords)
            return True
        except Exception as e:
            print(f"移除关键词失败: {e}")
            return False
    
    def batch_set_metadata(self, media_items, metadata):
        """批量设置元数据"""
        success_count = 0
        
        for item in media_items:
            if self.set_metadata(item, metadata):
                success_count += 1
        
        return success_count
    
    def batch_add_keyword(self, media_items, keyword):
        """批量添加关键词"""
        success_count = 0
        
        for item in media_items:
            if self.add_keyword(item, keyword):
                success_count += 1
        
        return success_count
```

### 4.2 标记系统

```python
class MarkerSystem:
    """标记系统"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def add_marker(self, media_item, frame, color="Red", note=""):
        """添加标记"""
        try:
            return media_item.AddMarker(frame, color, note)
        except Exception as e:
            print(f"添加标记失败: {e}")
            return False
    
    def remove_marker(self, media_item, frame):
        """移除标记"""
        try:
            return media_item.RemoveMarker(frame)
        except Exception as e:
            print(f"移除标记失败: {e}")
            return False
    
    def get_markers(self, media_item):
        """获取所有标记"""
        try:
            return media_item.GetMarkers()
        except Exception as e:
            print(f"获取标记失败: {e}")
            return []
    
    def clear_all_markers(self, media_item):
        """清除所有标记"""
        try:
            markers = self.get_markers(media_item)
            for marker in markers:
                media_item.RemoveMarker(marker["frame"])
            return True
        except Exception as e:
            print(f"清除标记失败: {e}")
            return False
    
    def set_marker_color(self, media_item, frame, color):
        """设置标记颜色"""
        try:
            return media_item.SetMarkerColor(frame, color)
        except Exception as e:
            print(f"设置标记颜色失败: {e}")
            return False
    
    def MARKER_COLORS = [
        "Red",      # 红色
        "Green",    # 绿色
        "Blue",     # 蓝色
        "Yellow",   # 黄色
        "Cyan",     # 青色
        "Magenta",  # 品红色
        "White"     # 白色
    ]
    
    def MARKER_FLAGS = [
        "Normal",       # 普通
        "Chapter",      # 章节
        "Comment",      # 注释
        "ToDo"          # 待办
    ]
```

---

## 五、代理工作流

### 5.1 代理生成与管理

```python
class ProxyWorkflow:
    """代理工作流"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def generate_proxy(self, media_item, resolution="1920x1080", format="DNxHR LB"):
        """生成代理"""
        try:
            return media_item.GenerateProxy(resolution, format)
        except Exception as e:
            print(f"生成代理失败: {e}")
            return False
    
    def batch_generate_proxy(self, media_items, resolution="1920x1080", format="DNxHR LB"):
        """批量生成代理"""
        success_count = 0
        
        for item in media_items:
            if self.generate_proxy(item, resolution, format):
                success_count += 1
        
        return success_count
    
    def attach_proxy(self, media_item, proxy_path):
        """附加代理"""
        try:
            return media_item.AttachProxy(proxy_path)
        except Exception as e:
            print(f"附加代理失败: {e}")
            return False
    
    def detach_proxy(self, media_item):
        """分离代理"""
        try:
            return media_item.DetachProxy()
        except Exception as e:
            print(f"分离代理失败: {e}")
            return False
    
    def enable_proxy_mode(self, enable=True):
        """启用/禁用代理模式"""
        try:
            project = self.engine.get_project()
            return project.SetProxyMode(enable)
        except Exception as e:
            print(f"设置代理模式失败: {e}")
            return False
    
    def get_proxy_status(self, media_item):
        """获取代理状态"""
        try:
            return {
                "has_proxy": media_item.HasProxy(),
                "proxy_path": media_item.GetProxyPath(),
                "proxy_enabled": media_item.IsProxyEnabled()
            }
        except Exception as e:
            print(f"获取代理状态失败: {e}")
            return {}
    
    def PROXY_RESOLUTIONS = [
        "720x406",       # 480p
        "1280x720",      # 720p
        "1920x1080",     # 1080p
        "2560x1440",     # 2K
        "3840x2160"      # 4K
    ]
    
    def PROXY_FORMATS = [
        "DNxHR LB",      # DNxHR低码率
        "DNxHR SQ",      # DNxHR标准质量
        "DNxHR HQ",      # DNxHR高质量
        "ProRes Proxy",  # ProRes代理
        "ProRes LT",     # ProRes LT
        "H.264",         # H.264
        "H.265"          # H.265
    ]
```

### 5.2 代理工作流自动化

```python
class ProxyAutomation:
    """代理工作流自动化"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.proxy_workflow = ProxyWorkflow(resolve_engine)
    
    def auto_proxy_workflow(self, folder_path, proxy_resolution="1920x1080"):
        """自动代理工作流"""
        try:
            # 初始化
            if not self.proxy_workflow.initialize():
                return False
            
            # 导入媒体
            importer = MediaImporter(self.engine)
            importer.initialize()
            
            media_items = importer.import_folder(folder_path)
            
            if not media_items:
                print("未找到媒体文件")
                return False
            
            # 批量生成代理
            success_count = self.proxy_workflow.batch_generate_proxy(
                media_items,
                proxy_resolution
            )
            
            print(f"成功生成 {success_count}/{len(media_items)} 个代理")
            
            # 启用代理模式
            self.proxy_workflow.enable_proxy_mode(True)
            
            return True
        except Exception as e:
            print(f"自动代理工作流失败: {e}")
            return False
    
    def switch_proxy_mode(self, enable):
        """切换代理模式"""
        return self.proxy_workflow.enable_proxy_mode(enable)
    
    def relink_proxy(self, media_item, new_proxy_path):
        """重新链接代理"""
        try:
            # 分离旧代理
            self.proxy_workflow.detach_proxy(media_item)
            
            # 附加新代理
            return self.proxy_workflow.attach_proxy(media_item, new_proxy_path)
        except Exception as e:
            print(f"重新链接代理失败: {e}")
            return False
```

---

## 六、媒体组织策略

### 6.1 文件夹组织规范

```python
class MediaOrganization:
    """媒体组织策略"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def create_project_structure(self, project_name):
        """创建项目文件夹结构"""
        try:
            root_folder = self.media_pool.GetRootFolder()
            
            # 创建基础文件夹结构
            folders = [
                f"{project_name}_Footage",
                f"{project_name}_Audio",
                f"{project_name}_Images",
                f"{project_name}_Graphics",
                f"{project_name}_Projects",
                f"{project_name}_Exports"
            ]
            
            created_folders = []
            for folder_name in folders:
                folder = self.media_pool.AddSubFolder(root_folder, folder_name)
                if folder:
                    created_folders.append(folder)
            
            # 在Footage下创建子文件夹
            footage_folder = self._find_folder_by_name(folders[0])
            if footage_folder:
                subfolders = ["Raw", "Edited", "Proxy", "Archive"]
                for sub in subfolders:
                    self.media_pool.AddSubFolder(footage_folder, sub)
            
            return created_folders
        except Exception as e:
            print(f"创建项目结构失败: {e}")
            return []
    
    def _find_folder_by_name(self, name, parent_folder=None):
        """查找文件夹"""
        search_folder = parent_folder or self.media_pool.GetRootFolder()
        
        for subfolder in search_folder.GetSubFolderList():
            if subfolder.GetName() == name:
                return subfolder
        
        return None
    
    def organize_by_date(self, media_items):
        """按日期组织"""
        try:
            root_folder = self.media_pool.GetRootFolder()
            date_folders = {}
            
            for item in media_items:
                metadata = item.GetMetadata()
                date_str = metadata.get("Date", "Unknown")
                
                if date_str not in date_folders:
                    date_folders[date_str] = self.media_pool.AddSubFolder(
                        root_folder, date_str
                    )
                
                # 移动到对应日期文件夹
                self.media_pool.MoveMediaItem(item, date_folders[date_str])
            
            return True
        except Exception as e:
            print(f"按日期组织失败: {e}")
            return False
    
    def organize_by_type(self, media_items):
        """按类型组织"""
        try:
            root_folder = self.media_pool.GetRootFolder()
            type_folders = {
                "Video": None,
                "Audio": None,
                "Images": None,
                "Other": None
            }
            
            # 创建类型文件夹
            for folder_name in type_folders.keys():
                type_folders[folder_name] = self.media_pool.AddSubFolder(
                    root_folder, folder_name
                )
            
            # 分类媒体
            for item in media_items:
                media_type = item.GetType()
                
                if media_type == "Video":
                    target = type_folders["Video"]
                elif media_type == "Audio":
                    target = type_folders["Audio"]
                elif media_type == "Still":
                    target = type_folders["Images"]
                else:
                    target = type_folders["Other"]
                
                if target:
                    self.media_pool.MoveMediaItem(item, target)
            
            return True
        except Exception as e:
            print(f"按类型组织失败: {e}")
            return False
```

### 6.2 智能文件夹

```python
class SmartBinManager:
    """智能文件夹管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def create_smart_bin(self, name, criteria):
        """创建智能文件夹"""
        try:
            return self.media_pool.CreateSmartBin(name, criteria)
        except Exception as e:
            print(f"创建智能文件夹失败: {e}")
            return None
    
    def create_video_bin(self):
        """创建视频智能文件夹"""
        criteria = {
            "Type": "Video",
            "Match": "Any"
        }
        return self.create_smart_bin("All Videos", criteria)
    
    def create_audio_bin(self):
        """创建音频智能文件夹"""
        criteria = {
            "Type": "Audio",
            "Match": "Any"
        }
        return self.create_smart_bin("All Audio", criteria)
    
    def create_unused_bin(self):
        """创建未使用素材智能文件夹"""
        criteria = {
            "Used": False,
            "Match": "Any"
        }
        return self.create_smart_bin("Unused Media", criteria)
    
    def create_high_res_bin(self, min_resolution="1920x1080"):
        """创建高分辨率素材智能文件夹"""
        criteria = {
            "Resolution": {
                "Operator": ">=",
                "Value": min_resolution
            },
            "Match": "Any"
        }
        return self.create_smart_bin("High Resolution", criteria)
    
    def create_by_keyword_bin(self, keyword):
        """按关键词创建智能文件夹"""
        criteria = {
            "Keyword": keyword,
            "Match": "Any"
        }
        return self.create_smart_bin(f"Keyword: {keyword}", criteria)
    
    def delete_smart_bin(self, smart_bin):
        """删除智能文件夹"""
        try:
            return self.media_pool.DeleteSmartBin(smart_bin)
        except Exception as e:
            print(f"删除智能文件夹失败: {e}")
            return False
    
    def update_smart_bin(self, smart_bin, new_criteria):
        """更新智能文件夹"""
        try:
            return smart_bin.SetCriteria(new_criteria)
        except Exception as e:
            print(f"更新智能文件夹失败: {e}")
            return False
```

---

## 七、批量媒体操作

### 7.1 批量导入与转码

```python
class BatchMediaOperations:
    """批量媒体操作"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def batch_import_from_multiple_folders(self, folder_paths):
        """从多个文件夹批量导入"""
        try:
            all_items = []
            
            for folder_path in folder_paths:
                importer = MediaImporter(self.engine)
                importer.initialize()
                items = importer.import_folder(folder_path)
                all_items.extend(items)
            
            return all_items
        except Exception as e:
            print(f"批量导入失败: {e}")
            return []
    
    def batch_transcode(self, media_items, format="DNxHR HQ", resolution="1920x1080"):
        """批量转码"""
        try:
            transcoded_items = []
            
            for item in media_items:
                transcoded = item.Transcode(format, resolution)
                if transcoded:
                    transcoded_items.append(transcoded)
            
            return transcoded_items
        except Exception as e:
            print(f"批量转码失败: {e}")
            return []
    
    def batch_rename(self, media_items, prefix="Clip_", start_index=1):
        """批量重命名"""
        try:
            for i, item in enumerate(media_items, start=start_index):
                new_name = f"{prefix}{i:04d}"
                item.SetName(new_name)
            
            return True
        except Exception as e:
            print(f"批量重命名失败: {e}")
            return False
    
    def batch_delete_unused(self):
        """批量删除未使用媒体"""
        try:
            return self.media_pool.RemoveUnusedMedia()
        except Exception as e:
            print(f"删除未使用媒体失败: {e}")
            return False
    
    def batch_move_to_folder(self, media_items, target_folder):
        """批量移动到文件夹"""
        try:
            for item in media_items:
                self.media_pool.MoveMediaItem(item, target_folder)
            
            return True
        except Exception as e:
            print(f"批量移动失败: {e}")
            return False
    
    def batch_export_metadata(self, media_items, output_file):
        """批量导出元数据"""
        try:
            import json
            
            metadata_list = []
            for item in media_items:
                metadata = item.GetMetadata()
                metadata_list.append({
                    "name": item.GetName(),
                    "path": item.GetMediaPath(),
                    "metadata": metadata
                })
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(metadata_list, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"导出元数据失败: {e}")
            return False
    
    def batch_import_metadata(self, metadata_file):
        """批量导入元数据"""
        try:
            import json
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata_list = json.load(f)
            
            for item_data in metadata_list:
                # 查找对应的媒体项
                media_items = self.media_pool.GetMediaItemsInFolder(
                    self.media_pool.GetRootFolder()
                )
                
                for item in media_items:
                    if item.GetName() == item_data["name"]:
                        item.SetMetadata(item_data["metadata"])
                        break
            
            return True
        except Exception as e:
            print(f"导入元数据失败: {e}")
            return False
```

---

## 八、Media页面API自动化

### 8.1 Media页面自动化引擎

```python
class MediaPageAutomation:
    """Media页面自动化引擎"""
    
    def __init__(self):
        self.resolve = None
        self.project_manager = None
        self.project = None
        self.media_pool = None
    
    def initialize(self):
        """初始化Resolve"""
        import DaVinciResolveScript as bmd
        
        self.resolve = bmd.scriptapp("Resolve")
        if not self.resolve:
            return False
        
        self.project_manager = self.resolve.GetProjectManager()
        self.project = self.project_manager.GetCurrentProject()
        
        if not self.project:
            return False
        
        self.media_pool = self.project.GetMediaPool()
        return True
    
    def create_project_with_structure(self, project_name):
        """创建带结构的项目"""
        try:
            # 创建项目
            self.project = self.project_manager.CreateProject(project_name)
            
            if not self.project:
                return False
            
            self.media_pool = self.project.GetMediaPool()
            
            # 创建文件夹结构
            organizer = MediaOrganization(self)
            organizer.initialize()
            organizer.create_project_structure(project_name)
            
            return True
        except Exception as e:
            print(f"创建项目结构失败: {e}")
            return False
    
    def auto_import_and_organize(self, folder_path, project_name="AutoProject"):
        """自动导入并组织"""
        try:
            # 创建项目
            if not self.create_project_with_structure(project_name):
                return False
            
            # 导入媒体
            importer = MediaImporter(self)
            importer.initialize()
            media_items = importer.import_folder(folder_path)
            
            if not media_items:
                return False
            
            # 按类型组织
            organizer = MediaOrganization(self)
            organizer.initialize()
            organizer.organize_by_type(media_items)
            
            # 添加关键词
            metadata_manager = MetadataManager(self)
            metadata_manager.batch_add_keyword(media_items, "Imported")
            
            print(f"成功导入并组织 {len(media_items)} 个媒体文件")
            
            return True
        except Exception as e:
            print(f"自动导入组织失败: {e}")
            return False
    
    def generate_proxy_for_all(self, resolution="1920x1080"):
        """为所有媒体生成代理"""
        try:
            if not self.media_pool:
                return False
            
            # 获取所有媒体项
            all_items = []
            root_folder = self.media_pool.GetRootFolder()
            
            def collect_items(folder):
                all_items.extend(folder.GetMediaItems())
                for subfolder in folder.GetSubFolderList():
                    collect_items(subfolder)
            
            collect_items(root_folder)
            
            # 批量生成代理
            proxy_workflow = ProxyWorkflow(self)
            proxy_workflow.initialize()
            success_count = proxy_workflow.batch_generate_proxy(all_items, resolution)
            
            print(f"成功生成 {success_count}/{len(all_items)} 个代理")
            
            return True
        except Exception as e:
            print(f"批量生成代理失败: {e}")
            return False
```

### 8.2 脚本执行示例

```python
# Media页面自动化脚本示例

def run_media_page_automation():
    """运行Media页面自动化"""
    automation = MediaPageAutomation()
    
    if not automation.initialize():
        print("Resolve初始化失败")
        return
    
    # 创建项目
    success = automation.create_project_with_structure("MyProject")
    
    if not success:
        print("创建项目失败")
        return
    
    # 自动导入并组织
    success = automation.auto_import_and_organize(
        "D:/Footage/Project1",
        "Project1_Auto"
    )
    
    if not success:
        print("导入组织失败")
        return
    
    # 生成代理
    success = automation.generate_proxy_for_all("1280x720")
    
    if success:
        print("Media页面自动化完成")
    else:
        print("Media页面自动化失败")

if __name__ == "__main__":
    run_media_page_automation()
```

---

## 九、故障排查

### 9.1 常见问题与解决方案

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| **导入失败** | 文件格式不支持或路径错误 | 检查文件格式和路径 |
| **媒体离线** | 文件被移动或删除 | 使用重新链接功能 |
| **元数据丢失** | 导入时未包含元数据 | 重新导入并勾选元数据选项 |
| **代理生成失败** | 存储空间不足或格式不支持 | 清理空间或更换格式 |
| **智能文件夹不更新** | 缓存过期 | 刷新智能文件夹 |
| **批量操作失败** | 部分文件权限不足 | 检查文件权限 |

### 9.2 故障排查工具

```python
class MediaPageTroubleshooter:
    """Media页面故障排查"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def check_offline_media(self):
        """检查离线媒体"""
        offline_items = []
        
        try:
            root_folder = self.media_pool.GetRootFolder()
            
            def check_folder(folder):
                for item in folder.GetMediaItems():
                    if not item.IsOnline():
                        offline_items.append({
                            "name": item.GetName(),
                            "path": item.GetMediaPath(),
                            "status": "Offline"
                        })
                
                for subfolder in folder.GetSubFolderList():
                    check_folder(subfolder)
            
            check_folder(root_folder)
            
            return offline_items
        except Exception as e:
            print(f"检查离线媒体失败: {e}")
            return []
    
    def check_missing_proxy(self):
        """检查缺失代理"""
        missing_proxy = []
        
        try:
            root_folder = self.media_pool.GetRootFolder()
            
            def check_folder(folder):
                for item in folder.GetMediaItems():
                    if item.GetType() == "Video" and not item.HasProxy():
                        missing_proxy.append({
                            "name": item.GetName(),
                            "path": item.GetMediaPath()
                        })
                
                for subfolder in folder.GetSubFolderList():
                    check_folder(subfolder)
            
            check_folder(root_folder)
            
            return missing_proxy
        except Exception as e:
            print(f"检查缺失代理失败: {e}")
            return []
    
    def check_duplicate_files(self):
        """检查重复文件"""
        duplicates = {}
        
        try:
            root_folder = self.media_pool.GetRootFolder()
            
            def check_folder(folder):
                for item in folder.GetMediaItems():
                    file_path = item.GetMediaPath()
                    if file_path in duplicates:
                        duplicates[file_path].append(item.GetName())
                    else:
                        duplicates[file_path] = [item.GetName()]
                
                for subfolder in folder.GetSubFolderList():
                    check_folder(subfolder)
            
            check_folder(root_folder)
            
            # 筛选出重复项
            result = {k: v for k, v in duplicates.items() if len(v) > 1}
            return result
        except Exception as e:
            print(f"检查重复文件失败: {e}")
            return {}
    
    def relink_offline_media(self, offline_items, new_base_path):
        """重新链接离线媒体"""
        success_count = 0
        
        try:
            import os
            
            for item in offline_items:
                old_path = item["path"]
                file_name = os.path.basename(old_path)
                new_path = os.path.join(new_base_path, file_name)
                
                if os.path.exists(new_path):
                    if self.media_pool.RelinkMedia(item, new_path):
                        success_count += 1
            
            return success_count
        except Exception as e:
            print(f"重新链接失败: {e}")
            return 0
```

---

## 十、性能优化

### 10.1 Media页面性能优化策略

```python
class MediaPagePerformanceOptimizer:
    """Media页面性能优化"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
        self.media_pool = None
    
    def initialize(self):
        """初始化"""
        project = self.engine.get_project()
        self.media_pool = project.GetMediaPool()
        return self.media_pool is not None
    
    def optimize_media_cache(self):
        """优化媒体缓存"""
        try:
            project = self.engine.get_project()
            
            project.SetCacheSettings({
                "CacheMode": "Smart",
                "PreGenerateThumbnails": True,
                "ThumbnailQuality": "Medium",
                "CacheLocation": "D:/ResolveCache"
            })
            
            return True
        except Exception as e:
            print(f"优化媒体缓存失败: {e}")
            return False
    
    def regenerate_thumbnails(self, media_items):
        """重新生成缩略图"""
        try:
            for item in media_items:
                item.RegenerateThumbnail()
            
            return True
        except Exception as e:
            print(f"重新生成缩略图失败: {e}")
            return False
    
    def clear_media_cache(self):
        """清理媒体缓存"""
        try:
            self.resolve.ClearMediaCache()
            return True
        except Exception as e:
            print(f"清理媒体缓存失败: {e}")
            return False
    
    def optimize_media_storage(self):
        """优化媒体存储"""
        try:
            storages = self.resolve.GetMediaStorages()
            
            for storage in storages:
                storage.Optimize()
            
            return True
        except Exception as e:
            print(f"优化媒体存储失败: {e}")
            return False
    
    def reduce_metadata_load(self):
        """减少元数据加载"""
        try:
            project = self.engine.get_project()
            
            project.SetMetadataSettings({
                "LoadAllMetadata": False,
                "LoadKeywords": True,
                "LoadMarkers": True,
                "LoadBasicInfo": True
            })
            
            return True
        except Exception as e:
            print(f"减少元数据加载失败: {e}")
            return False
```

### 10.2 存储管理

```python
class StorageManager:
    """存储管理器"""
    
    def __init__(self, resolve_engine):
        self.engine = resolve_engine
    
    def add_media_storage(self, path, name=None):
        """添加媒体存储"""
        try:
            storage_name = name or os.path.basename(path)
            return self.engine.resolve.AddMediaStorage(path, storage_name)
        except Exception as e:
            print(f"添加媒体存储失败: {e}")
            return False
    
    def remove_media_storage(self, path):
        """移除媒体存储"""
        try:
            return self.engine.resolve.RemoveMediaStorage(path)
        except Exception as e:
            print(f"移除媒体存储失败: {e}")
            return False
    
    def get_media_storages(self):
        """获取所有媒体存储"""
        try:
            return self.engine.resolve.GetMediaStorages()
        except Exception as e:
            print(f"获取媒体存储失败: {e}")
            return []
    
    def check_storage_usage(self):
        """检查存储使用情况"""
        try:
            storages = self.get_media_storages()
            usage_info = []
            
            for storage in storages:
                usage_info.append({
                    "name": storage.GetName(),
                    "path": storage.GetPath(),
                    "used": storage.GetUsedSpace(),
                    "total": storage.GetTotalSpace(),
                    "free": storage.GetFreeSpace()
                })
            
            return usage_info
        except Exception as e:
            print(f"检查存储使用失败: {e}")
            return []
    
    def set_cache_storage(self, path):
        """设置缓存存储"""
        try:
            return self.engine.resolve.SetCacheStorage(path)
        except Exception as e:
            print(f"设置缓存存储失败: {e}")
            return False
```

---

## 附录：Media页面参数速查表

### 媒体项参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `Name` | str | 任意 | 媒体名称 |
| `MediaPath` | str | 文件路径 | 媒体文件路径 |
| `ProxyPath` | str | 文件路径 | 代理文件路径 |
| `Type` | str | Video/Audio/Still等 | 媒体类型 |
| `Duration` | int | 帧 | 媒体时长 |
| `FrameRate` | float | fps | 帧率 |
| `Width` | int | 像素 | 宽度 |
| `Height` | int | 像素 | 高度 |
| `IsOnline` | bool | True/False | 是否在线 |
| `HasProxy` | bool | True/False | 是否有代理 |

### 导入选项参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `CopyToMediaPool` | bool | True/False | 复制到媒体池 |
| `AutoImport` | bool | True/False | 自动导入 |
| `CreateSubfolders` | bool | True/False | 创建子文件夹 |
| `TranscodeOnImport` | bool | True/False | 导入时转码 |
| `TranscodeFormat` | str | 转码格式 | 转码格式名称 |
| `ProxyMode` | str | Off/Create/Attach | 代理模式 |
| `ProxyResolution` | str | 分辨率 | 代理分辨率 |

### 缓存参数

| 参数名称 | 类型 | 范围 | 说明 |
|---------|------|------|------|
| `CacheMode` | str | Smart/Off/All | 缓存模式 |
| `PreGenerateThumbnails` | bool | True/False | 预生成缩略图 |
| `ThumbnailQuality` | str | Low/Medium/High | 缩略图质量 |
| `CacheLocation` | str | 路径 | 缓存位置 |