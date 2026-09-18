"""输出产物注册与验证中心 (T1)

统一交付目录 DELIVERY_ROOT 下所有视频/工程产物的登记、ffprobe 可播放性
校验与清单(manifest)生成。

用法:
    from config.output_registry import OutputRegistry
    reg = OutputRegistry()
    reg.register("text_animation_preview.mp4", category="preview")
    results = reg.verify_all()      # ffprobe 逐项校验
    reg.save_manifest()             # 写 output_manifest.json
"""
import datetime
import json
import os
import subprocess
from typing import Any, Dict, List, Optional

DELIVERY_ROOT = "D:/AE-Work/文档/hybrid_pipeline"
MANIFEST_NAME = "output_manifest.json"


def _ffprobe(path: str) -> dict[str, Any]:
    """ffprobe 探测: 返回 {ok, duration, width, height, codec, error}"""
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", path,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", timeout=30)
        if r.returncode != 0:
            return {"ok": False, "error": (r.stderr or "ffprobe failed")[:200]}
        info = json.loads(r.stdout)
        v = next((s for s in info.get("streams", [])
                  if s.get("codec_type") == "video"), None)
        if v is None:
            return {"ok": False, "error": "no video stream"}
        return {
            "ok": True,
            "duration": float(info.get("format", {}).get("duration", 0)),
            "width": v.get("width"),
            "height": v.get("height"),
            "codec": v.get("codec_name"),
        }
    except FileNotFoundError:
        return {"ok": False, "error": "ffprobe not found"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:200]}


class OutputRegistry:
    """产物注册表: register → verify_all → save_manifest 闭环"""

    def __init__(self, delivery_root: str = DELIVERY_ROOT):
        self.root = delivery_root.replace("\\", "/")
        self.entries: list[dict[str, Any]] = []

    # ── 登记 ────────────────────────────────────────────────
    def register(self, path: str, name: str = "", category: str = "video",
                 meta: dict[str, Any] | None = None) -> dict[str, Any]:
        """登记产物。path 可为相对交付目录的文件名或绝对路径。"""
        abs_path = path if os.path.isabs(path) else os.path.join(self.root, path)
        abs_path = abs_path.replace("\\", "/")
        entry = {
            "name": name or os.path.basename(abs_path),
            "path": abs_path,
            "rel_path": (os.path.relpath(abs_path, self.root).replace("\\", "/")
                         if abs_path.startswith(self.root) else abs_path),
            "category": category,
            "size_kb": round(os.path.getsize(abs_path) / 1024, 1)
                       if os.path.exists(abs_path) else None,
            "registered_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "meta": meta or {},
        }
        # 同名去重(覆盖旧登记)
        self.entries = [e for e in self.entries if e["path"] != abs_path]
        self.entries.append(entry)
        return entry

    def scan_existing(self, exts=(".mp4", ".mov", ".mkv")) -> int:
        """扫描交付目录已有视频并自动登记, 返回新增数量"""
        if not os.path.isdir(self.root):
            return 0
        added = 0
        known = {e["path"] for e in self.entries}
        for fn in sorted(os.listdir(self.root)):
            if fn.lower().endswith(exts):
                p = os.path.join(self.root, fn).replace("\\", "/")
                if p not in known:
                    self.register(p, category="video")
                    added += 1
        return added

    # ── 校验 ────────────────────────────────────────────────
    def verify_all(self) -> list[dict[str, Any]]:
        """对全部登记项做存在性 + ffprobe 可播放性校验, 结果写回 entry"""
        results = []
        for e in self.entries:
            res: dict[str, Any] = {"name": e["name"], "path": e["path"]}
            if not os.path.exists(e["path"]):
                res["status"] = "MISSING"
            else:
                probe = _ffprobe(e["path"])
                res.update(probe)
                res["status"] = "OK" if probe["ok"] else "CORRUPT"
            e["verify"] = res
            results.append(res)
        return results

    def all_green(self) -> bool:
        """全部登记项存在且可播放"""
        return bool(self.entries) and all(
            r.get("status") == "OK" for r in self.verify_all())

    # ── 清单 ────────────────────────────────────────────────
    def save_manifest(self, out_path: str = "") -> str:
        """生成 output_manifest.json, 返回清单路径"""
        manifest = {
            "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "delivery_root": self.root,
            "total": len(self.entries),
            "green": sum(1 for e in self.entries
                         if e.get("verify", {}).get("status") == "OK"),
            "entries": self.entries,
        }
        target = out_path or os.path.join(self.root, MANIFEST_NAME)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return target

    def report(self) -> str:
        """人类可读校验报告"""
        lines = [f"OutputRegistry @ {self.root}",
                 f"{'状态':<8}{'名称':<40}{'时长':>8}{'分辨率':>14}"]
        for e in self.entries:
            v = e.get("verify") or {"status": "UNVERIFIED"}
            dur = f"{v.get('duration', 0):.1f}s" if v.get("duration") else "-"
            res_s = (f"{v.get('width')}x{v.get('height')}"
                     if v.get("width") else "-")
            lines.append(f"{v['status']:<8}{e['name']:<40}{dur:>8}{res_s:>14}")
        return "\n".join(lines)


_REG: OutputRegistry | None = None


def get_registry() -> OutputRegistry:
    """进程级单例"""
    global _REG
    if _REG is None:
        _REG = OutputRegistry()
    return _REG
