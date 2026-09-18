# -*- coding: utf-8 -*-
"""AE 高级运镜渲染通道 — 从 v22 验证过的双通道架构抽取 (2026-08-13)

v22 成片即此通道渲染(用户认可"细节质感")。核心价值:
  - FFmpeg zoompan 只能匀速运镜(机械生硬), AE 能做贝塞尔缓动关键帧
    (setTemporalEaseAtKey) + 运动模糊(motionBlur), 这是"细节质感"的来源。
  - 本模块把 v22 的 build_jsx / bridge_run_jsx / normalize_ae_clip 三个
    已验证函数 + 配置抽成可复用类, 供 v23 主引擎对"高级运镜镜头"切换通道。

高级运镜判据(继承 v22 AE_TECHS):
  zoom_back (推近再拉回, 贝塞尔) / pulse (onset 脉冲, 关键帧)
  后续可扩展 fast_pan 等。

用法:
  chan = AERenderChannel(out_dir, project_root)
  chan.build_and_render(ae_plan, fps) -> {idx: mp4_path}
  其中 ae_plan = {idx: {"source","source_start","render_dur","speed",
                        "tech","onsets","fps","resolution","color"}}
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import hmac
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from core.bridge_failure import BridgeFailure
from core.bridge_failure import from_reason as _bf_from_reason
from core.paths import ae_exe, aerender_exe, ffmpeg_bin, ffprobe_bin

# AE 2025 完整版 (AE 2026 目录是空壳, 只有1个脚本面板)
# 路径统一收口到 core/paths.py（AEK_AE_EXE / AEK_AERENDER / AEK_FFMPEG / AEK_FFPROBE 可覆盖）
AERENDER = aerender_exe()
AE_EXE = ae_exe()
FFMPEG = ffmpeg_bin()
FFPROBE = ffprobe_bin()

# 进入 AE 高级通道的运镜技巧
# 继承 v22: pulse(onset脉冲) / zoom_back(推近再拉回)
# 扩展(缩放型运镜, FFmpeg zoompan 只能匀速/二次方, AE 有真贝塞尔+运动模糊):
#   zoom_in(缓推) / push(快推) / zoom_out(缓拉)
# 位移型(pan_left/pan_right/diag_pan) 走 FFmpeg zoompan 位置插值, 不进 AE
AE_TECHS = {"pulse", "zoom_back", "zoom_in", "push", "zoom_out"}


def _js_str(s) -> str:
    """ExtendScript 路径: 统一正斜杠, 避免反斜杠转义问题"""
    return str(s).replace("\\", "/")


class AERenderChannel:
    """AE 高级运镜通道: JSX生成 → Bridge通信 → aerender → 规范化MP4"""

    def __init__(self, out_dir, project_root: str = r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault"):
        self.out_dir = Path(out_dir)
        self.project_root = Path(project_root)
        self.bridge_dir = self.project_root / ".ae-mcp-bridge"
        self.ae_dir = self.out_dir / "ae_raw"
        self.ae_dir.mkdir(parents=True, exist_ok=True)
        self.aep_path = self.out_dir / "ae_shots.aep"
        self.jsx_path = self.out_dir / "build_comps.jsx"
        self.failures: list[BridgeFailure] = []

    def _fail(self, reason: str, stage: str, on_fail_reason=None) -> None:
        """记录结构化失败 + 回调旧接口（向后兼容）。"""
        self.failures.append(_bf_from_reason(reason, stage))
        if on_fail_reason:
            on_fail_reason(reason)

    def get_failures(self) -> list[dict]:
        return [f.to_dict() for f in self.failures]

    # ────────────────────────────────────────────────────────────
    # 签名（与监听器 ae_mcp_listener.jsx 对齐）
    # ────────────────────────────────────────────────────────────
    def _load_secret(self) -> str:
        """监听器 SECRET_FILE = 项目根 .mcp_secret（fail-closed，无 secret 拒签）。"""
        for cand in (self.project_root / ".mcp_secret",
                     self.project_root / ".ae-mcp-bridge" / ".mcp_secret",
                     Path.home() / "Documents" / "ae-mcp-bridge" / ".mcp_secret"):
            try:
                if cand.exists():
                    txt = cand.read_text(encoding="utf-8").strip()
                    if txt:
                        return txt
            except OSError:
                continue
        return ""

    def _generate_signature(self, data: dict, secret: str) -> str:
        """HMAC-SHA256 hex。canonical = json.dumps(sort_keys, 紧凑分隔符)。"""
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False)
        return hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    # ────────────────────────────────────────────────────────────
    # AE 整片精修 Pass (2026-09-04): 单次 aerender 给全片所有镜头上
    # Glow 微光 + 胶片颗粒 — 比逐镜 AE 快 10-20 倍, 每镜都有插件级质感
    # ────────────────────────────────────────────────────────────
    def polish_pass(self, video_in: str, out_dir: str = "") -> str | None:
        import os
        od = Path(out_dir) if out_dir else self.out_dir
        od = od.resolve()  # aerender 把相对路径解析到自己安装目录 (2026-09-04 实测)
        od.mkdir(parents=True, exist_ok=True)
        aep = od / "polish.aep"
        out_avi = od / "polish.avi"
        out_mp4 = od / "polish.mp4"
        vin = str(video_in).replace(chr(92), "/")
        aeps = str(aep).replace(chr(92), "/")
        avis = str(out_avi).replace(chr(92), "/")
        jsx = f"""
(function() {{
  try {{
    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    app.newProject();
    var imp = app.project.importFile(new ImportOptions(new File("{vin}")));
    var comp = app.project.items.addComp("POLISH", imp.width, imp.height,
        1.0, imp.duration, imp.frameRate);
    comp.layers.add(imp);
    // 2026-09-04 三坑修复: ①addSolid 第6参是时长(秒), 传1.0只盖住第1秒
    //   ②中文版 AE 特效参数英文名访问返回 null — 必须 matchName 设值
    //   ③ADBE Add Grain 此版本不可脚本添加 — 用 ADBE Noise (Amount=4%)
    var adj = comp.layers.addSolid([1,1,1], "FX", imp.width, imp.height, 1.0, imp.duration);
    adj.adjustmentLayer = true;
    var fx = adj.property("Effects");
    var gl = fx.addProperty("ADBE Glo2");
    gl.property("ADBE Glo2-0003").setValue(8);    // Glow Radius
    gl.property("ADBE Glo2-0004").setValue(0.3);  // Glow Intensity
    var ns = fx.addProperty("ADBE Noise");
    ns.property("ADBE Noise-0001").setValue(4);   // Amount of Noise (%)
    app.project.save(new File("{aeps}"));
    "ok";
  }} catch(e) {{ "ERR:" + e.toString(); }}
}})
"""
        res = self._bridge_run_jsx(args={"script": jsx, "scriptContent": jsx},
                                   timeout=180)
        self._bridge_run_jsx(
            timeout=60, command="executeAtomScript",
            args={"script": "try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); 'c'; } catch(e) { String(e); }",
                  "scriptContent": "try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); 'c'; } catch(e) { String(e); }"})
        # 新工程无 RStemplate/OMtemplate (传了报"模板不存在"); 默认输出模块即
        # H.264 .mp4 (~16Mbps) — 无需 Lossless AVI + ffmpeg 转码两级 (2026-09-04 实测)
        r = subprocess.run([AERENDER, "-project", str(aep), "-comp", "POLISH",
                            "-output", str(out_mp4)],
                           capture_output=True, timeout=1800,
                           encoding="utf-8", errors="replace")  # aerender 中文输出 GBK, text=True 默认 utf-8 会崩 reader 线程
        if not out_mp4.exists() or out_mp4.stat().st_size < 10000:
            print("    [AE精修] aerender 失败, 回退原片")
            return None
        ok = True
        print(f"    [AE精修] OK: {out_mp4}")
        return str(out_mp4) if ok else None

    # ────────────────────────────────────────────────────────────
    # 主入口: 完整渲染 AE 高级运镜镜头, 返回 {idx: mp4_path}
    # ────────────────────────────────────────────────────────────
    def build_and_render(self, ae_plan: dict[int, dict], fps: int,
                         on_fail_reason=None) -> dict[int, str]:
        """ae_plan: {idx: {source, source_start, render_dur, speed, tech,
                           onsets, fps, resolution, color}}"""
        if not ae_plan or not Path(AERENDER).exists():
            self._fail("计划为空或aerender不存在", "preflight", on_fail_reason)
            return {}

        print(f"\n[AE通道] 生成JSX ({len(ae_plan)}镜头, 贝塞尔缓动+运动模糊)...")
        self._build_jsx(ae_plan, self.jsx_path, self.aep_path, self.ae_dir, fps)
        print(f"  JSX: {self.jsx_path}")

        # 确保 AE 运行
        if not self._ensure_ae_running():
            self._fail("AE未运行且启动失败", "ae_launch", on_fail_reason)
            return {}

        # Bridge 就绪检查 (监听器无 ping 分支, 用最小 executeAtomScript 探测)
        _probe_script = "app.version;"
        ping = self._bridge_run_jsx(timeout=90, command="executeAtomScript",
                                    args={"script": _probe_script, "scriptContent": _probe_script})
        if not (ping and ping.get("status") == "success"):
            print(f"  [WARN] Bridge 探测未成功({(ping or {}).get('message', '无响应')}), 仍尝试构建")

        # Bridge 构建合成
        print("[AE通道] Bridge 构建合成...")
        bridge_res = self._bridge_run_jsx(str(self.jsx_path), timeout=300)
        if bridge_res is None:
            self._fail("Bridge无响应(300s超时)", "bridge_build", on_fail_reason)
            return {}
        print(f"  Bridge: status={bridge_res.get('status', '')}")
        time.sleep(3)

        # 读取构建结果
        build_file = self.out_dir / "ae_build_result.json"
        build_info = None
        if build_file.exists():
            try:
                build_info = json.loads(build_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

        # 校验构建结果: 只要 ≥1 个合成成功构建就继续渲染。
        # 失败镜头(JSX 内 catch)不会进 renderQueue, aerender 只渲染成功的,
        # 规范化阶段对缺失 avi 已容错(返回 miss → 调用方 ffmpeg fallback)。
        # 此前用 >= len(ae_plan) 作门槛, 个别镜头失败会拖垮整个 AE 通道。
        if not (build_info and build_info.get("compCount", 0) >= 1):
            err = (build_info or {}).get("errors", []) if build_info else ["无构建结果"]
            self._fail(f"合成构建失败: {err}", "build_validate", on_fail_reason)
            return {}
        _errs = (build_info or {}).get("errors", [])
        if _errs:
            print(f"  [AE通道] {len(_errs)}个镜头构建失败, 将 fallback ffmpeg: {_errs}")

        # aerender 前关闭 AE 内工程 (避免 AE/aerender 同时持有同一工程)
        _close_script = ("try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); 'closed'; } "
                         "catch(e) { String(e); }")
        self._bridge_run_jsx(timeout=60, command="executeAtomScript",
                             args={"script": _close_script, "scriptContent": _close_script})

        # aerender 渲染
        print("[AE通道] aerender 渲染...")
        t0 = time.time()
        r = subprocess.run([AERENDER, "-project", str(self.aep_path)],
                           capture_output=True, text=True, timeout=1800,
                           encoding="utf-8", errors="ignore")
        print(f"  aerender: rc={r.returncode}, 耗时{time.time() - t0:.0f}s")

        # 规范化 (并行4线程: 精确帧数 + 调色)
        print("[AE通道] 规范化AE片段 (并行4线程)...")
        ae_clips: dict[int, str] = {}

        def _norm_one(idx, p):
            comp_name = f"shot_{idx:03d}"
            avi = self.ae_dir / f"{comp_name}.avi"
            out_mp4 = self.ae_dir / f"{comp_name}.mp4"
            if not avi.exists():
                return idx, "miss", f"shot{idx}: aerender未输出"
            if self._normalize_ae_clip(avi, out_mp4, p):
                return idx, "ok", None
            return idx, "fail", f"shot{idx}: 规范化/帧数校验失败"

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futs = {pool.submit(_norm_one, idx, p): idx for idx, p in sorted(ae_plan.items())}
            for fut in concurrent.futures.as_completed(futs):
                idx, st, err = fut.result()
                if st == "ok":
                    ae_clips[idx] = str(self.ae_dir / f"shot_{idx:03d}.mp4")
                    p = ae_plan[idx]
                    print(f"    shot{idx:02d}: [OK] {p['render_dur']:.3f}s → "
                          f"{int(round(p['render_dur']*p['fps']))}帧")
                else:
                    self._fail(err, "normalize", on_fail_reason)
        return ae_clips

    # ────────────────────────────────────────────────────────────
    # 内部: 三件套 (从 v22 原样抽取)
    # ────────────────────────────────────────────────────────────
    def _ensure_ae_running(self, auto_launch: bool = False) -> bool:
        """确保 AE 运行 (tasklist 检查)。

        auto_launch=False (默认): AE 未运行直接返回 False → 调用方快速 fallback
        ffmpeg 通道, 不自动启动 AE (避免首启弹窗 + 强杀崩溃风险, 不拖慢流程)。
        auto_launch=True: 显式请求时无参启动 AE 并等待 90s (v22 原行为)。
        """
        ae_running = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq AfterFX.exe"],
            capture_output=True, text=True, timeout=15,
            encoding="gbk", errors="ignore")
        if "AfterFX.exe" in (ae_running.stdout or ""):
            return True
        if not auto_launch:
            print("[AE通道] AE未运行 — 快速降级 ffmpeg 通道 (不自动启动, 防弹窗/崩溃)")
            return False
        print("[AE通道] AE未运行, 启动中...")
        if self.aep_path.exists():
            self.aep_path.unlink()
        subprocess.Popen([AE_EXE])
        print("  等待AE加载 90s...")
        time.sleep(90)
        return True

    def _bridge_run_jsx(self, jsx_path=None, timeout=300, command="executeAtomScript", args=None):
        """Bridge协议: 清残留→写命令→轮询结果 (记忆: 残留命令毒杀bridge)

        2026-09-01 协议对齐: 监听器白名单只有 executeAtomScript 且经
        new Function(scriptStr) 执行 — 不认 runScript、不吃 {file:...}。
        → 默认命令改 executeAtomScript; 传 jsx 文件时读全文作 args.script。
        """
        cmd_file = self.bridge_dir / "ae_command.json"
        # 结果文件兼容两个监听器: 主监听器写 ae_result.json,
        # bg_listener 写 ae_mcp_result.json。读时都清 + 都读。
        res_files = [self.bridge_dir / "ae_result.json",
                     self.bridge_dir / "ae_mcp_result.json"]
        for f in ([cmd_file] + res_files):
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass
        if args is None:
            if jsx_path is None:
                args = {}
            else:
                # 监听器 executeScript 是 new Function(字符串) — 必须传脚本全文
                # 文件带 BOM(ExtendScript 识别中文需 BOM)但 eval 字符串不能带 \ufeff
                jsx_text = Path(jsx_path).read_text(encoding="utf-8-sig")
                # script: 主监听器 (ae_mcp_listener.jsx) 读 args.script
                # scriptContent: bg_listener (ae_mcp_bg_listener.jsx) 读 args.scriptContent
                args = {"script": jsx_text.lstrip("\ufeff"),
                        "scriptContent": jsx_text.lstrip("\ufeff")}
        cmd = {
            "command": command,
            "args": args,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S") + f".{int(time.time()*1e6)%1000000:06d}",
            "status": "pending",
        }
        # 签名验证 (2026-09-01): 监听器 SIGNATURE_ENABLED=true fail-closed,
        # 无签名命令直接拒绝。规范与 ae/ae_bridge_base._generate_signature 一致:
        # HMAC-SHA256 hex + canonical json(sort_keys, 紧凑分隔符)。
        secret = self._load_secret()
        if secret:
            sign_data = {k: v for k, v in cmd.items() if k != "signature" and k != "signature_alg"}
            cmd["signature"] = self._generate_signature(sign_data, secret)
        cmd_file.write_text(json.dumps(cmd, ensure_ascii=False, indent=2), encoding="utf-8")
        t0 = time.time()
        while time.time() - t0 < timeout:
            for rf in res_files:
                if rf.exists():
                    try:
                        return json.loads(rf.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, OSError):
                        time.sleep(1)
                        continue
            time.sleep(2)
        return None

    def _build_jsx(self, plan, out_jsx, aep_path, ae_dir, fps):
        """生成单条JSX: 逐镜头建comp(精确帧数) → 贝塞尔关键帧 → 运动模糊 → 渲染队列"""
        lines = []
        lines.append("// AE高级运镜通道 — 自动生成 (ES3)")
        lines.append("var V22 = {};")
        lines.append("V22.fps = " + str(fps) + ";")
        lines.append("V22.errors = [];")
        lines.append("V22.footageCache = {};")
        lines.append("V22.compCount = 0;")
        lines.append("V22.aepPath = " + json.dumps(_js_str(aep_path)) + ";")
        lines.append("(function () {")
        lines.append("  try { app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES); } catch (e0) {}")
        lines.append("  app.newProject();")
        lines.append("  app.beginUndoGroup('ae_build');")
        lines.append("  try {")
        lines.append("    var shots = [")
        for idx in sorted(plan.keys()):
            p = plan[idx]
            shot = {
                "idx": idx, "src": _js_str(p["source"]),
                "srcStart": round(p["source_start"], 3),
                "dur": round(p["render_dur"], 4), "speed": round(p["speed"], 4),
                "tech": p["tech"], "onsets": [round(o, 3) for o in p.get("onsets", [])],
            }
            lines.append("      " + json.dumps(shot, ensure_ascii=False) + ",")
        lines.append("    ];")
        lines.append("    function getFootage(path) {")
        lines.append("      if (V22.footageCache[path]) { return V22.footageCache[path]; }")
        lines.append("      var f = new File(path);")
        lines.append("      if (!f.exists) { throw new Error('素材不存在: ' + path); }")
        lines.append("      var io = new ImportOptions(f);")
        lines.append("      io.forceAlphabeticalImport = true;")
        lines.append("      var item = app.project.importFile(io);")
        lines.append("      V22.footageCache[path] = item;")
        lines.append("      return item;")
        lines.append("    }")
        lines.append("    function ez(speed, influence) { return new KeyframeEase(speed, influence); }")
        lines.append("    function scaleVal(sp, s) {")
        lines.append("      var n = sp.value.length;")
        lines.append("      var v = [];")
        lines.append("      for (var vi = 0; vi < n; vi++) { v.push(s); }")
        lines.append("      return v;")
        lines.append("    }")
        lines.append("    function easeN(sp, e) {")
        lines.append("      var n = sp.value.length;")
        lines.append("      var arr = [];")
        lines.append("      for (var ai = 0; ai < n; ai++) { arr.push(e); }")
        lines.append("      return arr;")
        lines.append("    }")
        lines.append("    function applyEase(sp, eIn, eOut) {")
        lines.append("      for (var ek = 1; ek <= sp.numKeys; ek++) {")
        lines.append("        sp.setTemporalEaseAtKey(ek, easeN(sp, eIn), easeN(sp, eOut));")
        lines.append("      }")
        lines.append("    }")
        lines.append("    for (var i = 0; i < shots.length; i++) {")
        lines.append("      var shot = shots[i];")
        lines.append("      var nFrames = Math.round(shot.dur * V22.fps);")
        lines.append("      if (nFrames < 2) { nFrames = 2; }")
        lines.append("      var compName = 'shot_' + ('00' + shot.idx).slice(-3);")
        lines.append("      try {")
        lines.append("        var comp = app.project.items.addComp(compName, 1920, 1080, 1.0, nFrames / V22.fps, V22.fps);")
        lines.append("        comp.motionBlur = true;")
        lines.append("        comp.motionBlurAdaptive = true;")
        lines.append("        comp.motionBlurSamplesPerFrame = 16;")
        lines.append("        var foot = getFootage(shot.src);")
        lines.append("        var layer = comp.layers.add(foot);")
        lines.append("        layer.motionBlur = true;")
        lines.append("        if (Math.abs(shot.speed - 1.0) > 0.01) {")
        lines.append("          layer.stretch = 100.0 / shot.speed;")
        lines.append("        }")
        lines.append("        layer.startTime = -(shot.srcStart * layer.stretch / 100.0);")
        lines.append("        layer.inPoint = 0;")
        lines.append("        layer.outPoint = comp.duration;")
        lines.append("        var aw = layer.width, ah = layer.height;")
        lines.append("        layer.property('Anchor Point').setValue([aw / 2, ah / 2]);")
        lines.append("        layer.property('Position').setValue([960, 540]);")
        lines.append("        var baseScale = Math.max(1920 / aw, 1080 / ah) * 100 * 1.02;")
        lines.append("        var sp = layer.property('Scale');")
        lines.append("        var tMid = comp.duration / 2;")
        lines.append("        if (shot.tech === 'zoom_back') {")
        lines.append("          sp.setValueAtTime(0, scaleVal(sp, baseScale));")
        lines.append("          sp.setValueAtTime(tMid, scaleVal(sp, baseScale * 1.2));")
        lines.append("          sp.setValueAtTime(comp.duration, scaleVal(sp, baseScale));")
        lines.append("          applyEase(sp, ez(0, 33), ez(0, 33));")
        lines.append("        } else if (shot.tech === 'zoom_in') {")
        lines.append("          sp.setValueAtTime(0, scaleVal(sp, baseScale));")
        lines.append("          sp.setValueAtTime(comp.duration, scaleVal(sp, baseScale * 1.25));")
        lines.append("          sp.setTemporalEaseAtKey(1, easeN(sp, ez(0, 0.1)), easeN(sp, ez(0, 75)));")
        lines.append("          sp.setTemporalEaseAtKey(2, easeN(sp, ez(0, 75)), easeN(sp, ez(0, 0.1)));")
        lines.append("        } else if (shot.tech === 'push') {")
        lines.append("          sp.setValueAtTime(0, scaleVal(sp, baseScale));")
        lines.append("          sp.setValueAtTime(comp.duration, scaleVal(sp, baseScale * 1.3));")
        lines.append("          sp.setTemporalEaseAtKey(1, easeN(sp, ez(0, 0.1)), easeN(sp, ez(0, 10)));")
        lines.append("          sp.setTemporalEaseAtKey(2, easeN(sp, ez(0, 90)), easeN(sp, ez(0, 0.1)));")
        lines.append("        } else if (shot.tech === 'zoom_out') {")
        lines.append("          sp.setValueAtTime(0, scaleVal(sp, baseScale * 1.3));")
        lines.append("          sp.setValueAtTime(comp.duration, scaleVal(sp, baseScale));")
        lines.append("          applyEase(sp, ez(0, 33), ez(0, 33));")
        lines.append("        } else {")
        lines.append("          sp.setValueAtTime(0, scaleVal(sp, baseScale));")
        lines.append("          var lastT = 0;")
        lines.append("          for (var oi = 0; oi < shot.onsets.length; oi++) {")
        lines.append("            var t0 = shot.onsets[oi];")
        lines.append("            if (t0 <= lastT + 0.1) { continue; }")
        lines.append("            sp.setValueAtTime(t0, scaleVal(sp, baseScale * 1.25));")
        lines.append("            sp.setValueAtTime(t0 + 0.08, scaleVal(sp, baseScale));")
        lines.append("            lastT = t0 + 0.08;")
        lines.append("          }")
        lines.append("          sp.setValueAtTime(comp.duration, scaleVal(sp, baseScale));")
        lines.append("          var nk = sp.numKeys;")
        lines.append("          for (var k2 = 1; k2 <= nk; k2++) {")
        lines.append("            sp.setTemporalEaseAtKey(k2, easeN(sp, ez(0, 10)), easeN(sp, ez(0, 60)));")
        lines.append("          }")
        lines.append("        }")
        lines.append("        var rqItem = app.project.renderQueue.items.add(comp);")
        lines.append("        var om = rqItem.outputModule(1);")
        lines.append("        var tplNames = om.templates;")
        lines.append("        var picked = '';")
        lines.append("        for (var ti = 0; ti < tplNames.length; ti++) {")
        lines.append("          var tn = tplNames[ti];")
        lines.append("          if (tn === 'Lossless' || tn === '\u65e0\u635f') { picked = tn; break; }")
        lines.append("        }")
        lines.append("        if (picked !== '') { om.applyTemplate(picked); }")
        lines.append("        else { om.format = 'AVI'; }")
        lines.append("        om.file = new File(" + json.dumps(_js_str(str(ae_dir))) + " + '/' + compName + '.avi');")
        lines.append("        V22.compCount += 1;")
        lines.append("      } catch (e2) {")
        lines.append("        V22.errors.push(compName + ': ' + e2.message);")
        lines.append("      }")
        lines.append("    }")
        lines.append("    app.project.save(File(V22.aepPath));")
        lines.append("  } catch (e) {")
        lines.append("    V22.errors.push('fatal: ' + e.message + ' line:' + e.line);")
        lines.append("  }")
        lines.append("  app.endUndoGroup();")
        lines.append("})();")
        lines.append("(function () {")
        lines.append("  var rs = '{\"compCount\":' + V22.compCount + ',\"errors\":[';")
        lines.append("  for (var ei = 0; ei < V22.errors.length; ei++) {")
        lines.append("    if (ei > 0) { rs += ','; }")
        lines.append("    rs += '\"' + String(V22.errors[ei]).replace(/\"/g, \"'\").replace(/\\n/g, ' ') + '\"';")
        lines.append("  }")
        lines.append("  rs += ']}';")
        lines.append("  var rf = new File(" + json.dumps(_js_str(str(self.out_dir / "ae_build_result.json"))) + ");")
        lines.append("  rf.encoding = 'UTF-8';")
        lines.append("  if (rf.open('w')) { rf.write(rs); rf.close(); }")
        lines.append("})();")
        content = "\ufeff" + "\n".join(lines)  # UTF-8 BOM 确保中文路径
        Path(out_jsx).write_text(content, encoding="utf-8")
        return str(out_jsx)

    def _normalize_ae_clip(self, avi_path, out_path, p) -> bool:
        """AE无损AVI → 精确规格MP4: 帧数=round(render_dur*fps), 调色与ffmpeg通道同款"""
        n_frames = max(2, int(round(p["render_dur"] * p["fps"])))
        sat = p["color"].get("saturation", 1.2)
        con = p["color"].get("contrast", 1.05)
        bri = p["color"].get("brightness", 0.0)
        w, h = p["resolution"]
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        vf += f"eq=saturation={sat}:contrast={con}:brightness={bri}"
        cmd = [FFMPEG, "-y", "-i", str(avi_path), "-vf", vf,
               "-r", str(p["fps"]), "-frames:v", str(n_frames),
               "-c:v", "libx264", "-preset", "slow", "-b:v", "50M",
               "-maxrate", "60M", "-bufsize", "100M", "-minrate", "40M",
               "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="ignore")
        if r.returncode != 0 or not Path(out_path).exists():
            return False
        rp = subprocess.run([FFPROBE, "-v", "error", "-count_frames",
                             "-select_streams", "v:0",
                             "-show_entries", "stream=nb_read_frames",
                             "-of", "csv=p=0", str(out_path)],
                            capture_output=True, text=True, timeout=60,
                            encoding="utf-8", errors="ignore")
        got = int(rp.stdout.strip()) if rp.returncode == 0 and rp.stdout.strip().isdigit() else -1
        return got == n_frames
