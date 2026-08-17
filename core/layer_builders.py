from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from .edit_fx_vocabulary import speed_ramp_jsx

def js_str(value: str) -> str:
    return str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r').replace('\t','\\t')

def _hex_to_rgb(value: str) -> List[float]:
    value = value.lstrip('#'); return [int(value[i:i+2],16)/255 for i in (0,2,4)]
@dataclass
class LayerBuildContext:
    tree: Any
    warnings: List[str]
    post_lines: List[str]

def _var(layer): return f"layer{layer.z_index}"
def _bounds(layer): return float(layer.time_range[0]), float(layer.time_range[1])
def _header(ctx, layer, kind):
    var=_var(layer); t0,t1=_bounds(layer)
    return [f'    var {var} = comp.layers.add{kind};', f'    {var}.startTime = {t0};', f'    {var}.outPoint = {t1};']

def _layer_name(layer): return js_str(getattr(layer, 'name', getattr(layer, 'id', 'Layer')))

def build_solid_layer(ctx, layer):
    var=_var(layer); t0,t1=_bounds(layer); c=layer.content.get('color',[0,0,0]); rgb=[x/255 if x>1 else x for x in c]
    return [f'    var {var} = comp.layers.addSolid([{rgb[0]:.4f},{rgb[1]:.4f},{rgb[2]:.4f}], "{_layer_name(layer)}", comp.width, comp.height, 1.0, comp.duration);', f'    {var}.startTime = {t0};', f'    {var}.outPoint = {t1};']

def build_adjustment_layer(ctx, layer):
    lines=_header(ctx,layer,'Solid([0,0,0], "'+_layer_name(layer)+'", comp.width, comp.height, 1.0, comp.duration)'); var=_var(layer); lines.insert(1,f'    {var}.adjustmentLayer = true;')
    if layer.content.get('edit_fx_layer') == 'grain': lines += [f'    var _noise_{var} = {var}.effect.addProperty("ADBE Noise");', f'    _noise_{var}.property(1).setValue({layer.content.get("amount",12)});']
    for effect in getattr(layer, 'effects', []):
        if effect.kind == 'combo': lines.append(f'    function __fxAdd_{var}(name) {{ return {var}.effect.addProperty(name); }}')
        lines.append(f'    var _fx_{var} = {var}.effect.addProperty("{js_str(effect.name)}");')
    return lines

def build_text_layer(ctx, layer):
    var=_var(layer); t0,t1=_bounds(layer); c=layer.content.get('colors',{}).get('main','#FFFFFF')
    font=layer.content.get('font','auto'); chain=[font] if font != 'auto' else []
    chain += ['SourceHanSansCN-Bold','Arial']
    fonts='['+','.join('"'+js_str(x)+'"' for x in dict.fromkeys(chain))+']'
    rgb = _hex_to_rgb(c)
    color = f"[{rgb[0]:.4f}, {rgb[1]:.4f}, {rgb[2]:.4f}]"
    lines = [
        f'    var {var} = comp.layers.addText("{js_str(layer.content.get("text", ""))}");',
        f'    {var}.startTime = {t0};',
        f'    {var}.outPoint = {t1};',
        f'    var _doc_{var} = {var}.property("ADBE Text Properties").property("ADBE Text Document");',
        f'    _doc_{var}.setValue(_doc_{var}.value);',
        f'    _doc_{var}.value.fontSize = {layer.content.get("size", 72)};',
        f'    _doc_{var}.value.fillColor = {color};',
        f'    var _fonts_{var} = {fonts}; var _fontOk = false; for (var _fi=0; _fi<_fonts_{var}.length; _fi++) {{ try {{ _doc_{var}.value.font = _fonts_{var}[_fi]; _fontOk=true; break; }} catch(_e) {{}} }}',
    ]
    if getattr(layer, 'animations', {}).get('entrance'):
        lines += [f'    {var}.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime({t0}, 0);', f'    {var}.property("ADBE Transform Group").property("ADBE Opacity").setValueAtTime({min(t1, t0 + 0.4)}, 100);']
    lines.append(f'    {var}.property("ADBE Transform Group").property("ADBE Position");')
    for effect in getattr(layer, 'effects', []):
        lines.append(f'    var _fx_{var} = {var}.effect.addProperty("{js_str(effect.name)}");')
    return lines


def build_footage_layer(ctx, layer):
    var=_var(layer); t0,t1=_bounds(layer); content=layer.content; src=float(content.get('source_in',0)); lines=[f'    var _io{var} = new ImportOptions(new File("{js_str(content.get("path",""))}"));', f'    var {var}_ftg = app.project.importFile(_io{var});', f'    var {var} = comp.layers.add({var}_ftg);', f'    var proj = app.project; proj.importFile(_io{var});']
    has_ramps=bool(content.get('speed_ramps'))
    start=t0 if has_ramps else t0-src
    lines = ([*lines, f'    if (!{var}_ftg.mainSource.hasVideo) {{ throw new Error("素材无视频轨"); }}'] if not content.get('allow_still') else lines)
    lines += [f'    {var}.startTime = {start};', f'    {var}.inPoint = {t0};', f'    {var}.outPoint = {t1};', f'    {var}.outPoint = Math.min({t1}, {var}_ftg.duration);']
    if not content.get('allow_still'):
        lines.append(f'    // hasVideo validated for {var}_ftg')
    if content.get('speed_ramps'): lines.append(speed_ramp_jsx(var, float(content.get('source_dur',t1-t0)), content['speed_ramps'], offset=t0, source_in=src))
    lines.append(f'    {var}.property("ADBE Transform Group").property("ADBE Scale").setValue([100,100]);')
    fit = content.get('fit', 'cover')
    scale_fn = 'max' if fit == 'cover' else 'min'
    lines.append(f'    var _scale_{var} = Math.{scale_fn}(comp.width/{var}_ftg.width, comp.height/{var}_ftg.height);')
    lines.append(f'    // {fit} scale: Math.{scale_fn}(comp.width/{var}_ftg.width, comp.height/{var}_ftg.height)')
    if content.get('matting_mode') == 'track_matte' and content.get('matte_dir'):
        matte_path = js_str(content['matte_dir'])
        mio = f'_mio{layer.z_index}'
        lines += [f'    var {mio} = new ImportOptions(new File("{matte_path}")); {mio}.sequence = true;', f'    var {var}_matte = comp.layers.add(app.project.importFile({mio}));', f'    var {mio} = new ImportOptions(new File("{matte_path}")); {mio}.sequence = true;', f'    {mio}.sequence = true;']
    if content.get('matting_mode') == 'track_matte':
        if content.get('matte_dir'):
            ctx.post_lines += [f'    layer{layer.z_index}_matte.moveAfter({var});', f'    {var}.trackMatteType = TrackMatteType.ALPHA;']
        else: ctx.warnings.append('track_matte 缺少 matte_dir')
    return lines

def build_particle_layer(ctx, layer):
    var=_var(layer); t0,t1=_bounds(layer); return [f'    var {var} = comp.layers.addSolid([0,0,0], "{_layer_name(layer)}", comp.width, comp.height, 1.0, comp.duration);', f'    {var}.blendingMode = BlendingMode.ADD;', f'    {var}.startTime = {t0};', f'    {var}.outPoint = {t1};', f'    // CC Particle World template: {js_str(layer.content.get("template","spark"))}']
LAYER_BUILDERS={'solid':build_solid_layer,'adjustment':build_adjustment_layer,'text':build_text_layer,'footage':build_footage_layer,'particle':build_particle_layer}
def build_layer(ctx, layer):
    if layer.type not in LAYER_BUILDERS: raise ValueError(f'未知图层类型: {layer.type}')
    return LAYER_BUILDERS[layer.type](ctx, layer)
