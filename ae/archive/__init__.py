# -*- coding: utf-8 -*-
"""ae.archive — 08-29 事故后最小重建（2026-09-10）。

原 ``ae.archive`` 目录（自研 Bridge 协议归档实现）在 2026-08-29 工作区
清空事故中丢失——该目录从未入库（git ls-tree 全历史无记录），无法从
任何备份恢复。本包按调用方实测接口面最小重建：

- bridge_protocol: 枚举/数据类/常量完整还原；BridgeClient 提供构造与
  send_command 接口，实际文件桥执行明确报错（协议已弃用，迁移到
  开源 after-effects-mcp，新代码用 ae.unified_ae_client）。
- bridge_middleware: MiddlewarePipeline + 5 个中间件（透传语义）。

重建原则：导入面 100% 兼容（ae/ps|pr|au_mcp_client 及兼容转发模块
ae/bridge_protocol.py 等），执行面诚实失败而非静默假装可用。
"""
