"""ai/director_feedback_hook.py - v23 导演真实参数反馈写入

修复 D2: director 路径不经过 unified_pipeline._trigger_param_feedback,
导致 param_feedback.json 自 08-11 起零真实写入(仅有 20 条 inject_* 种子)。
本 hook 在导演渲染成功后将变速/效果真实参数与内容级质量分写入 FeedbackStore。
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict


def _store_path() -> Path:
    """反馈存储路径, 支持环境变量覆盖(测试用)"""
    env = os.environ.get("PARAM_FEEDBACK_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "learning" / ".cache" / "param_feedback.json"


def record_director_feedback(run_info: Dict[str, Any]) -> int:
    """将一次导演运行的真实参数写入反馈库。返回写入条数。

    run_info 应包含:
        - run_id: 运行标识
        - quality: 内容级质量分(0-100)
        - ramps: 变速/效果参数列表, 每项含 type + 具体参数
        - style: 风格名称(可选)
    """
    path = _store_path()
    data = {"version": "1.0", "records": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"version": "1.0", "records": []}

    quality = float(run_info.get("quality", 0.0))
    rating = round(max(0.0, min(1.0, quality / 100.0)), 3)
    style = run_info.get("style")
    written = 0

    for ramp in run_info.get("ramps", []):
        rec = {
            "record_id": f"director_{run_info.get('run_id', 'unknown')}_{uuid.uuid4().hex[:6]}",
            "effect_name": ramp.get("type", "speed_ramp"),
            "style_name": style,
            "parameters": {k: v for k, v in ramp.items() if k != "type"},
            "rating": rating,
            "adjustment": None,
            "timestamp": time.time(),
            "metadata": {
                "source": "director_v23",
                "run_id": run_info.get("run_id"),
            },
        }
        data["records"].append(rec)
        written += 1

    if written:
        data["updated_at"] = time.time()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return written
