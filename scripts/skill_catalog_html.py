# -*- coding: utf-8 -*-
"""skill_catalog_html.py — 技能清单静态分发页生成器（P2-13 社区分发面 MVP）。

消费 schemas/skill_cards/registry.json + 全部卡片 YAML，产出单文件 HTML：
  四标签 = 全景卡片墙 / 功能域分组 / 无头能力矩阵 / 成本计量表
  能力   = 全文搜索、stage/headless/cost 筛选、详情抽屉（契约+证据链+禁忌）
参考 CutLedger·SkillsHub 四标签台账形态，但数据维度更强（证据链/无头/成本）。

用法: python scripts/skill_catalog_html.py [--out portfolio/skills/index.html]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CARDS_DIR = ROOT / "schemas" / "skill_cards"
REGISTRY = CARDS_DIR / "registry.json"

HTML_TMPL = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AE-Knowledge-Vault · 技能台账 Skills Ledger</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--dim:#8b949e;
--active:#3fb950;--validated:#58a6ff;--experimental:#d29922;--deprecated:#f85149;--archived:#6e7681;
--headless:#3fb950;--host:#d29922;--gui:#f85149;--gpu:#bc8cff;--paid:#f778ba}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font:14px/1.6 -apple-system,'Segoe UI','Microsoft YaHei',sans-serif}
header{padding:28px 32px 18px;border-bottom:1px solid var(--border)}
h1{font-size:22px;letter-spacing:.5px}
.sub{color:var(--dim);margin-top:6px;font-size:13px}
.stats{display:flex;gap:14px;margin-top:14px;flex-wrap:wrap}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:110px}
.stat b{font-size:20px;display:block}.stat span{color:var(--dim);font-size:12px}
nav{display:flex;gap:4px;padding:12px 32px;border-bottom:1px solid var(--border);flex-wrap:wrap}
nav button{background:none;border:1px solid transparent;color:var(--dim);padding:7px 16px;border-radius:6px;cursor:pointer;font-size:14px}
nav button.on{color:var(--text);background:var(--panel);border-color:var(--border)}
.toolbar{padding:14px 32px 0;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.toolbar input{background:var(--panel);border:1px solid var(--border);color:var(--text);padding:8px 12px;border-radius:6px;width:280px}
.toolbar select{background:var(--panel);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:6px}
main{padding:18px 32px 60px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer;transition:border-color .15s}
.card:hover{border-color:#58a6ff}
.card h3{font-size:15px;font-family:ui-monospace,Consolas,monospace;word-break:break-all}
.card .use{color:var(--dim);font-size:12.5px;margin-top:6px;height:38px;overflow:hidden}
.badges{display:flex;gap:6px;margin-top:10px;flex-wrap:wrap}
.b{font-size:11px;padding:2px 8px;border-radius:10px;border:1px solid}
.b.active{color:var(--active);border-color:var(--active)}.b.validated{color:var(--validated);border-color:var(--validated)}
.b.experimental{color:var(--experimental);border-color:var(--experimental)}.b.deprecated{color:var(--deprecated);border-color:var(--deprecated)}
.b.archived{color:var(--archived);border-color:var(--archived)}
.b.headless{color:var(--headless);border-color:var(--headless)}.b.requires_running_host{color:var(--host);border-color:var(--host)}
.b.requires_gui{color:var(--gui);border-color:var(--gui)}
.b.gpu_local{color:var(--gpu);border-color:var(--gpu)}.b.api_paid{color:var(--paid);border-color:var(--paid)}
.b.plain{color:var(--dim);border-color:var(--border)}
.domain-sec h2{font-size:16px;margin:26px 0 12px;color:var(--validated)}
table{width:100%;border-collapse:collapse;margin-top:8px}
th,td{border:1px solid var(--border);padding:9px 12px;text-align:left;font-size:13px}
th{background:var(--panel);color:var(--dim)}
td a{color:var(--validated);cursor:pointer}
.drawer{position:fixed;top:0;right:-560px;width:560px;max-width:92vw;height:100vh;background:var(--panel);border-left:1px solid var(--border);transition:right .25s;z-index:10;overflow-y:auto;padding:24px}
.drawer.open{right:0}
.drawer h2{font-family:ui-monospace,Consolas,monospace;font-size:17px;word-break:break-all}
.drawer .close{float:right;background:none;border:1px solid var(--border);color:var(--dim);border-radius:6px;padding:4px 10px;cursor:pointer}
.drawer h4{margin:18px 0 6px;color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:1px}
.drawer pre{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:12px;font-size:12px;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9;display:none}.overlay.on{display:block}
.note{color:var(--dim);font-size:12.5px;margin:10px 0}
mark{background:#9e6a03;color:#fff;border-radius:2px}
</style></head>
<body>
<header>
  <h1>⚙️ AE-Knowledge-Vault · 技能台账 <span style="color:var(--dim);font-weight:normal;font-size:14px">Skills Ledger</span></h1>
  <div class="sub">剪辑自动化能力单元的活卡片体系 —— 每张卡带参数契约、执行证据链、无头能力与成本画像。数据源 <code>schemas/skill_cards/</code>，生成于 __DATE__。</div>
  <div class="stats" id="stats"></div>
</header>
<nav id="tabs">
  <button data-t="wall" class="on">全景卡片墙</button>
  <button data-t="domain">功能域分组</button>
  <button data-t="matrix">无头能力矩阵</button>
  <button data-t="cost">成本计量表</button>
</nav>
<div class="toolbar" id="toolbar">
  <input id="q" placeholder="搜索 skill_id / 用途 / 域 …">
  <select id="fStage"><option value="">stage 全部</option></select>
  <select id="fHeadless"><option value="">无头能力 全部</option></select>
  <select id="fCost"><option value="">成本 全部</option></select>
  <span class="note" id="count"></span>
</div>
<main id="main"></main>
<div class="overlay" id="ov" onclick="closeDrawer()"></div>
<aside class="drawer" id="drawer"></aside>
<script>
const DATA = __DATA__;
const CARDS = DATA.cards, SUM = DATA.summary;
const $=s=>document.querySelector(s);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let TAB='wall';

function badge(v,cls){return `<span class="b ${cls||''}">${esc(v)}</span>`}
function cardHtml(c){
  return `<div class="card" onclick="openDrawer('${esc(c.skill_id)}')">
    <h3>${esc(c.skill_id)}</h3>
    <div class="use">${esc((c.intended_use||'').slice(0,90))}</div>
    <div class="badges">${badge(c.stage)}${badge(c.headless)}${badge(c.cost?.class)}
      ${badge(c.domain,'plain')}${badge(c.skill_type,'plain')}
      ${c.evidence_chain?.status==='real_execution'?'<span class="b active">✓ 实测</span>':''}</div>
  </div>`;
}
function filtered(){
  const q=$('#q').value.trim().toLowerCase(), st=$('#fStage').value, hd=$('#fHeadless').value, co=$('#fCost').value;
  return CARDS.filter(c=>{
    if(st&&c.stage!==st)return false; if(hd&&c.headless!==hd)return false; if(co&&c.cost?.class!==co)return false;
    if(q&&!(c.skill_id+' '+(c.intended_use||'')+' '+c.domain+' '+(c.tags||[]).join(' ')).toLowerCase().includes(q))return false;
    return true;});
}
function hl(text){ // 简单高亮
  const q=$('#q').value.trim(); if(!q)return esc(text);
  return esc(text).replaceAll(esc(q),`<mark>${esc(q)}</mark>`);
}
function render(){
  const rows=filtered();
  $('#count').textContent=`${rows.length} / ${CARDS.length} 张`;
  const m=$('#main');
  if(TAB==='wall'){m.innerHTML=`<div class="grid">${rows.map(c=>cardHtml(c)).join('')}</div>`;}
  else if(TAB==='domain'){
    const g={};rows.forEach(c=>{(g[c.domain]=g[c.domain]||[]).push(c)});
    m.innerHTML=Object.keys(g).sort().map(d=>`<div class="domain-sec"><h2>${esc(d)}（${g[d].length}）</h2><div class="grid">${g[d].map(c=>cardHtml(c)).join('')}</div></div>`).join('');
  }
  else if(TAB==='matrix'){
    const H=['headless','requires_running_host','requires_gui'];
    let html=`<p class="note">无头能力矩阵：编排器据此预判"要不要先开宿主应用"。headless=可全自动无界面；requires_running_host=宿主进程须在（AE listener / Resolve / ComfyUI…）。</p><table><tr><th>skill</th><th>stage</th>${H.map(h=>`<th>${h}</th>`).join('')}<th>host</th></tr>`;
    rows.forEach(c=>{html+=`<tr><td><a onclick="openDrawer('${esc(c.skill_id)}')">${esc(c.skill_id)}</a></td><td>${badge(c.stage)}</td>${H.map(h=>`<td>${c.headless===h?'✅':'·'}</td>`).join('')}<td>${(c.requires_host||[]).map(x=>esc(x.app)).join(',')}</td></tr>`});
    m.innerHTML=html+'</table>';
  }
  else{ // cost
    let html=`<p class="note">成本计量：free_local=本地零成本；gpu_local=占 GPU；api_paid=外部 API 计费。typical=单次典型耗时。</p><table><tr><th>skill</th><th>cost class</th><th>typical (s)</th><th>headless</th><th>备注</th></tr>`;
    rows.forEach(c=>{html+=`<tr><td><a onclick="openDrawer('${esc(c.skill_id)}')">${esc(c.skill_id)}</a></td><td>${badge(c.cost?.class)}</td><td>${c.cost?.typical_duration_sec??'-'}</td><td>${esc(c.headless)}</td><td>${esc((c.cost?.notes||'').slice(0,60))}</td></tr>`});
    m.innerHTML=html+'</table>';
  }
}
function openDrawer(id){
  const c=CARDS.find(x=>x.skill_id===id);if(!c)return;
  const ec=c.evidence_chain||{};
  $('#drawer').innerHTML=`<button class="close" onclick="closeDrawer()">✕</button>
    <h2>${esc(c.skill_id)}</h2>
    <div class="badges" style="margin:10px 0">${badge(c.stage)}${badge(c.headless)}${badge(c.cost?.class)}${badge(c.skill_type,'plain')}</div>
    <h4>用途</h4><div>${esc(c.intended_use)}</div>
    <h4>禁忌 / 边界</h4><div style="color:#f0883e">${esc(c.out_of_scope||'—')}</div>
    <h4>宿主要求</h4><div>${(c.requires_host||[]).map(x=>`${esc(x.app)} ${esc(x.version)}`).join('，')||'—'}</div>
    <h4>参数契约 contract.inputs</h4><pre>${esc(JSON.stringify(c.contract?.inputs||{},null,1).slice(0,2400))}</pre>
    <h4>证据链 evidence_chain</h4><pre>${esc(JSON.stringify(ec,null,1).slice(0,1600))}</pre>
    <h4>实现引用 recipe_ref</h4><pre>${esc(c.recipe_ref||c.tool_ref?.gateway_tool||'—')}</pre>
    ${c.checksum?`<h4>校验和</h4><pre>${esc(c.checksum)}</pre>`:''}
    <h4>版本史</h4><pre>${esc(JSON.stringify(c.version_history||[],null,1).slice(0,800))}</pre>`;
  $('#drawer').classList.add('open');$('#ov').classList.add('on');
}
function closeDrawer(){$('#drawer').classList.remove('open');$('#ov').classList.remove('on')}
function initStats(){
  const n=CARDS.length;
  const by=k=>CARDS.reduce((a,c)=>{const v=k==='cost'?c.cost?.class:c[k];a[v]=(a[v]||0)+1;return a},{});
  const st=by('stage'),hd=by('headless'),co=by('cost');
  const verified=CARDS.filter(c=>c.evidence_chain?.status==='real_execution').length;
  $('#stats').innerHTML=[
    [`<b>${n}</b><span>技能卡总数</span>`],
    [`<b style="color:var(--active)">${st.active||0}</b><span>active 可投产</span>`],
    [`<b style="color:var(--validated)">${verified}</b><span>附真实执行证据</span>`],
    [`<b style="color:var(--headless)">${hd.headless||0}</b><span>可无头执行</span>`],
    [`<b style="color:var(--gpu)">${co.gpu_local||0}</b><span>GPU 成本项</span>`],
    [`<b>${new Set(CARDS.map(c=>c.domain)).size}</b><span>功能域</span>`],
  ].map(x=>`<div class="stat">${x[0]}</div>`).join('');
  const fill=(id,vals)=>{const s=$(id);vals.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.appendChild(o)})};
  fill('#fStage',[...new Set(CARDS.map(c=>c.stage))]);
  fill('#fHeadless',[...new Set(CARDS.map(c=>c.headless))]);
  fill('#fCost',[...new Set(CARDS.map(c=>c.cost?.class))]);
}
document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{
  document.querySelectorAll('#tabs button').forEach(x=>x.classList.remove('on'));
  b.classList.add('on');TAB=b.dataset.t;render();});
['#q','#fStage','#fHeadless','#fCost'].forEach(id=>{$(id).addEventListener('input',render)});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer()});
initStats();render();
</script></body></html>
"""


def build(out_path: Path) -> int:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    cards = []
    for sid, entry in sorted(reg["skills"].items()):
        f = ROOT / entry["path"]
        if f.exists():
            cards.append(yaml.safe_load(f.read_text(encoding="utf-8")))
    html = (HTML_TMPL
            .replace("__DATE__", date.today().isoformat())
            .replace("__DATA__", json.dumps({"cards": cards, "summary": reg["summary"]},
                                            ensure_ascii=False)))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"技能台账已生成: {out_path}（{len(cards)} 卡，{out_path.stat().st_size/1024:.0f}KB）")
    return len(cards)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="portfolio/skills/index.html")
    a = ap.parse_args()
    n = build(ROOT / a.out)
    return 0 if n else 1


if __name__ == "__main__":
    sys.exit(main())
