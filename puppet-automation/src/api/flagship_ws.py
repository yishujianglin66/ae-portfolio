"""
puppet-automation/src/api/flagship_ws.py — 旗舰管线 WebSocket 管理器
====================================================================

管理旗舰管线执行的实时状态推送：
- 每 10s 推送 status 增量
- 支持多客户端同时监听同一 run
- 断连后客户端降级为 5s 轮询
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


class FlagshipWSManager:
    """旗舰管线 WebSocket 连接管理器。"""

    def __init__(self):
        # run_id -> set of active websocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        # run_id -> latest status payload
        self._status_cache: Dict[str, Dict[str, Any]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        """接受 WebSocket 连接。"""
        await websocket.accept()
        if run_id not in self._connections:
            self._connections[run_id] = set()
        self._connections[run_id].add(websocket)
        logger.info(f"[FlagshipWS] Client connected to run={run_id}")

        # 立即推送缓存状态
        if run_id in self._status_cache:
            await websocket.send_text(json.dumps(self._status_cache[run_id]))

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        """移除断开的连接。"""
        if run_id in self._connections:
            self._connections[run_id].discard(websocket)
            if not self._connections[run_id]:
                del self._connections[run_id]
        logger.info(f"[FlagshipWS] Client disconnected from run={run_id}")

    async def broadcast(self, run_id: str, status: Dict[str, Any]) -> None:
        """向指定 run 的所有客户端广播状态。"""
        self._status_cache[run_id] = status
        connections = self._connections.get(run_id, set()).copy()
        dead: List[WebSocket] = []

        for ws in connections:
            try:
                await ws.send_text(json.dumps(status))
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(run_id, ws)

    def update_status(self, run_id: str, status: Dict[str, Any]) -> None:
        """更新缓存状态（不推送，等待下次广播周期）。"""
        self._status_cache[run_id] = status

    def get_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取缓存的最新状态。"""
        return self._status_cache.get(run_id)

    def has_connections(self, run_id: str) -> bool:
        """是否有活跃连接。"""
        return bool(self._connections.get(run_id))

    def cleanup(self, run_id: str) -> None:
        """清理指定 run 的所有连接和缓存。"""
        self._connections.pop(run_id, None)
        self._status_cache.pop(run_id, None)


# 全局单例
flagship_ws_manager = FlagshipWSManager()
