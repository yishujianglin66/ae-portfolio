"""
模型注册中心 - 模型版本管理、元数据管理、上线/下线、A/B测试支持
参考 Antares 哲学：精悍够用，小步快跑，持续迭代
"""
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """模型信息
    
    包含模型的完整元数据，用于版本管理和部署决策。
    """
    model_name: str
    """模型名称"""
    model_version: str
    """模型版本（语义化版本号）"""
    model_type: str
    """模型类型：jsx_code, style_classify, param_optim 等"""
    model_path: str
    """模型文件路径"""
    base_model: str
    """基座模型名称"""
    training_method: str
    """训练方法：lora, full_finetune 等"""
    params_million: float = 0.0
    """参数量（百万）"""
    train_samples: int = 0
    """训练样本数"""
    eval_metrics: dict[str, float] = field(default_factory=dict)
    """评估指标"""
    cost_effectiveness: float = 0.0
    """成本效益比（Antares 核心指标）"""
    training_time_hours: float = 0.0
    """训练时间（小时）"""
    training_cost_usd: float = 0.0
    """训练成本（美元）"""
    created_at: str = ""
    """创建时间"""
    status: str = "staging"
    """状态：staging, production, deprecated, archived"""
    description: str = ""
    """模型描述"""
    tags: list[str] = field(default_factory=list)
    """标签"""
    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")


class ModelRegistry:
    """模型注册中心
    
    提供：
    - 模型版本管理
    - 模型元数据管理
    - 模型上线/下线
    - A/B 测试支持
    
    参考 Antares 哲学：小步快跑，持续迭代，用数据驱动模型升级。
    """

    def __init__(self, registry_path: str | None = None):
        """初始化模型注册中心

        Args:
            registry_path: 注册中心存储路径。
                默认使用项目稳定路径 data/model_lifecycle (2026-08-14 修复:
                原 "./model_registry" 为 cwd 相对路径, 曾导致 4 份散落副本)。
        """
        if registry_path is None:
            registry_path = str(
                Path(__file__).resolve().parent.parent.parent
                / "data" / "model_lifecycle")
        self.registry_path = registry_path
        self._models: dict[str, dict[str, ModelInfo]] = {}
        self._production_models: dict[str, str] = {}
        self._ab_tests: dict[str, dict[str, Any]] = {}

        os.makedirs(self.registry_path, exist_ok=True)
        self._load_registry()

    def sync_from_inventory(self, inventory_path: str | None = None) -> dict[str, int]:
        """从资产清单 (models/model_registry.json) 同步到生命周期注册中心。

        两层分工 (2026-08-14 统一方案):
          - 资产清单 = "盘上有什么" (路径/尺寸/任务) → 唯一事实源
          - 生命周期注册中心 = "哪个版本可用" (staging/production/A-B) → 决策层
        桥接规则:
          - 清单新增模型 → 登记一条 "inventory" 版本, status="staging"
          - 已有登记 → 仅回填 model_path / metadata.inventory (不动生命周期状态)

        Args:
            inventory_path: 资产清单路径, 默认 models/model_registry.json

        Returns:
            {"added": n, "updated": n}
        """
        if inventory_path is None:
            inventory_path = str(
                Path(__file__).resolve().parent.parent.parent
                / "models" / "model_registry.json")
        if not os.path.exists(inventory_path):
            logger.warning("inventory not found: %s", inventory_path)
            return {"added": 0, "updated": 0}
        try:
            with open(inventory_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("inventory read failed: %s", e)
            return {"added": 0, "updated": 0}

        added = updated = 0
        for entry in data.get("models", []):
            mid = entry.get("id") or entry.get("name")
            if not mid:
                continue
            _inventory_meta = {
                k: entry.get(k)
                for k in ("task", "type", "size_mb", "source", "status")
            }
            existing = self._models.get(mid, {}).get("inventory")
            if existing is not None:
                existing.model_path = entry.get("path") or existing.model_path
                existing.metadata["inventory"] = _inventory_meta
                updated += 1
            else:
                self._models.setdefault(mid, {})["inventory"] = ModelInfo(
                    model_name=mid,
                    model_version="inventory",
                    model_type=entry.get("type", "unknown"),
                    model_path=entry.get("path", ""),
                    base_model=entry.get("source", ""),
                    training_method="external",
                    status="staging",
                    description=entry.get("task", ""),
                    metadata={"inventory": _inventory_meta},
                )
                added += 1
        self._save_registry()
        logger.info("sync_from_inventory: added=%d updated=%d", added, updated)
        return {"added": added, "updated": updated}

    def _load_registry(self) -> None:
        """从磁盘加载注册中心数据"""
        registry_file = os.path.join(self.registry_path, "registry.json")
        
        if os.path.exists(registry_file):
            try:
                with open(registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for model_name, versions in data.get('models', {}).items():
                    self._models[model_name] = {}
                    for version, info_dict in versions.items():
                        self._models[model_name][version] = ModelInfo(**info_dict)
                
                self._production_models = data.get('production_models', {})
                self._ab_tests = data.get('ab_tests', {})
                
                logger.info(f"Loaded registry: {len(self._models)} models")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
        else:
            logger.info("No existing registry found, starting fresh")

    def _save_registry(self) -> None:
        """保存注册中心数据到磁盘"""
        registry_file = os.path.join(self.registry_path, "registry.json")
        
        try:
            data = {
                'models': {
                    name: {
                        version: asdict(info)
                        for version, info in versions.items()
                    }
                    for name, versions in self._models.items()
                },
                'production_models': self._production_models,
                'ab_tests': self._ab_tests,
                'updated_at': time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info("Registry saved successfully")
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def register_model(self, model_info: ModelInfo) -> str:
        """注册新模型
        
        Args:
            model_info: 模型信息
            
        Returns:
            str: 模型唯一标识（name:version）
        """
        model_name = model_info.model_name
        version = model_info.model_version
        
        if model_name not in self._models:
            self._models[model_name] = {}
        
        if version in self._models[model_name]:
            logger.warning(f"Model {model_name}:{version} already exists, overwriting")
        
        self._models[model_name][version] = model_info
        self._save_registry()
        
        model_id = f"{model_name}:{version}"
        logger.info(f"Registered model: {model_id}")
        return model_id

    def get_model(self, model_name: str, version: str | None = None) -> ModelInfo | None:
        """获取模型信息
        
        Args:
            model_name: 模型名称
            version: 版本号，None 表示获取生产版本或最新版本
            
        Returns:
            Optional[ModelInfo]: 模型信息
        """
        if model_name not in self._models:
            return None
        
        if version is None:
            if model_name in self._production_models:
                version = self._production_models[model_name]
            else:
                version = self._get_latest_version(model_name)
        
        if version is None:
            return None
        
        return self._models[model_name].get(version)

    def _get_latest_version(self, model_name: str) -> str | None:
        """获取最新版本号
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[str]: 最新版本号
        """
        if model_name not in self._models or not self._models[model_name]:
            return None
        
        versions = list(self._models[model_name].keys())
        versions.sort(reverse=True)
        return versions[0]

    def list_models(self, model_type: str | None = None, status: str | None = None) -> list[ModelInfo]:
        """列出模型
        
        Args:
            model_type: 按模型类型过滤
            status: 按状态过滤
            
        Returns:
            List[ModelInfo]: 模型列表
        """
        result = []
        
        for model_name, versions in self._models.items():
            for version, info in versions.items():
                if model_type and info.model_type != model_type:
                    continue
                if status and info.status != status:
                    continue
                result.append(info)
        
        return result

    def list_versions(self, model_name: str) -> list[str]:
        """列出模型的所有版本
        
        Args:
            model_name: 模型名称
            
        Returns:
            List[str]: 版本列表（降序）
        """
        if model_name not in self._models:
            return []
        
        versions = list(self._models[model_name].keys())
        versions.sort(reverse=True)
        return versions

    def promote_to_production(self, model_name: str, version: str) -> bool:
        """将模型升级为生产版本
        
        Args:
            model_name: 模型名称
            version: 版本号
            
        Returns:
            bool: 是否成功
        """
        if model_name not in self._models or version not in self._models[model_name]:
            logger.error(f"Model {model_name}:{version} not found")
            return False
        
        old_version = self._production_models.get(model_name)
        
        self._production_models[model_name] = version
        self._models[model_name][version].status = "production"
        
        if old_version and old_version != version and old_version in self._models[model_name]:
            self._models[model_name][old_version].status = "deprecated"
        
        self._save_registry()
        logger.info(f"Promoted {model_name}:{version} to production")
        return True

    def deprecate_model(self, model_name: str, version: str) -> bool:
        """废弃模型版本
        
        Args:
            model_name: 模型名称
            version: 版本号
            
        Returns:
            bool: 是否成功
        """
        if model_name not in self._models or version not in self._models[model_name]:
            logger.error(f"Model {model_name}:{version} not found")
            return False
        
        self._models[model_name][version].status = "deprecated"
        
        if self._production_models.get(model_name) == version:
            del self._production_models[model_name]
        
        self._save_registry()
        logger.info(f"Deprecated {model_name}:{version}")
        return True

    def archive_model(self, model_name: str, version: str) -> bool:
        """归档模型版本
        
        Args:
            model_name: 模型名称
            version: 版本号
            
        Returns:
            bool: 是否成功
        """
        if model_name not in self._models or version not in self._models[model_name]:
            logger.error(f"Model {model_name}:{version} not found")
            return False
        
        self._models[model_name][version].status = "archived"
        
        if self._production_models.get(model_name) == version:
            del self._production_models[model_name]
        
        self._save_registry()
        logger.info(f"Archived {model_name}:{version}")
        return True

    def get_production_model(self, model_name: str) -> ModelInfo | None:
        """获取生产环境模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[ModelInfo]: 生产模型信息
        """
        if model_name not in self._production_models:
            return None
        
        version = self._production_models[model_name]
        return self._models[model_name].get(version)

    def start_ab_test(
        self,
        test_name: str,
        model_name: str,
        version_a: str,
        version_b: str,
        traffic_split: tuple[float, float] = (0.5, 0.5),
    ) -> bool:
        """启动 A/B 测试
        
        Args:
            test_name: 测试名称
            model_name: 模型名称
            version_a: A 版本
            version_b: B 版本
            traffic_split: 流量分配 (A比例, B比例)
            
        Returns:
            bool: 是否成功
        """
        if model_name not in self._models:
            logger.error(f"Model {model_name} not found")
            return False
        
        if version_a not in self._models[model_name]:
            logger.error(f"Version {version_a} not found")
            return False
        
        if version_b not in self._models[model_name]:
            logger.error(f"Version {version_b} not found")
            return False
        
        self._ab_tests[test_name] = {
            'model_name': model_name,
            'version_a': version_a,
            'version_b': version_b,
            'traffic_split_a': traffic_split[0],
            'traffic_split_b': traffic_split[1],
            'start_time': time.strftime("%Y-%m-%d %H:%M:%S"),
            'status': 'running',
            'metrics': {},
        }
        
        self._save_registry()
        logger.info(f"Started A/B test: {test_name}")
        return True

    def stop_ab_test(self, test_name: str, winner: str | None = None) -> dict[str, Any]:
        """停止 A/B 测试
        
        Args:
            test_name: 测试名称
            winner: 获胜版本（'A' 或 'B'），None 表示不指定
            
        Returns:
            Dict[str, Any]: 测试结果
        """
        if test_name not in self._ab_tests:
            logger.error(f"A/B test {test_name} not found")
            return {}
        
        test_info = self._ab_tests[test_name]
        test_info['status'] = 'completed'
        test_info['end_time'] = time.strftime("%Y-%m-%d %H:%M:%S")
        test_info['winner'] = winner
        
        self._save_registry()
        logger.info(f"Stopped A/B test: {test_name}, winner: {winner}")
        
        return test_info

    def get_ab_test(self, test_name: str) -> dict[str, Any] | None:
        """获取 A/B 测试信息
        
        Args:
            test_name: 测试名称
            
        Returns:
            Optional[Dict[str, Any]]: 测试信息
        """
        return self._ab_tests.get(test_name)

    def get_best_model(
        self,
        model_type: str,
        metric: str = "cost_effectiveness",
    ) -> ModelInfo | None:
        """获取最佳模型（基于指定指标）
        
        Antares 哲学：选择成本效益比最高的模型，而不是单纯效果最好的。
        
        Args:
            model_type: 模型类型
            metric: 评估指标
            
        Returns:
            Optional[ModelInfo]: 最佳模型信息
        """
        best_model = None
        best_score = -float('inf')
        
        for model_name, versions in self._models.items():
            for version, info in versions.items():
                if info.model_type != model_type:
                    continue
                
                if info.status in ('archived',):
                    continue
                
                if metric == 'cost_effectiveness':
                    score = info.cost_effectiveness
                elif metric in info.eval_metrics:
                    score = info.eval_metrics[metric]
                else:
                    continue
                
                if score > best_score:
                    best_score = score
                    best_model = info
        
        return best_model


def load_registry(registry_path: str | None = None,
                  sync: bool = False) -> "ModelRegistry":
    """以稳定默认路径 (data/model_lifecycle) 加载生命周期注册中心。

    供训练/评估脚本复用, 避免各脚本自行拼 cwd 相对路径导致副本散落。

    Args:
        registry_path: 显式覆盖存储路径 (默认 data/model_lifecycle)
        sync: True 时先执行 sync_from_inventory() 把资产清单桥接进来
            (幂等: 新增登记 staging, 已有仅回填路径/元数据)
    """
    reg = ModelRegistry(registry_path)
    if sync:
        reg.sync_from_inventory()
    return reg
