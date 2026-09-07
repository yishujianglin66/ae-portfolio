# -*- coding: utf-8 -*-
"""ModelScope 关键词搜索：whisper-tiny / DWPose / face-parse-bisent 镜像。"""
from modelscope.hub.api import HubApi

api = HubApi()
for kw in ["whisper-tiny", "DWPose", "dw-ll_ucoco", "face-parse", "bisent", "MuseTalk"]:
    print("=" * 50)
    print("搜索:", kw)
    try:
        models = api.list_models(query=kw)
        rows = list(models) if hasattr(models, "__iter__") else []
        for m in rows[:8]:
            name = getattr(m, "Name", None) or getattr(m, "Path", None) or str(m)
            print("  -", str(name)[:80])
        if not rows:
            print("  (无结果)")
    except Exception as e:
        print("  ERROR:", str(e)[:120])
