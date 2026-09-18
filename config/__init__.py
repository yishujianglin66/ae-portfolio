# -*- coding: utf-8 -*-
"""
配置包 - 集中管理生产/开发/测试环境配置
"""

from .settings import Settings, settings

# 兼容别名：新代码/测试用 app_settings 指代单例实例，
# 避免与 Settings 类产生命名混淆（回归防护见 test_regression_guards）
app_settings = settings

__all__ = ["settings", "app_settings", "Settings"]
