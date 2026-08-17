from typing import Any, Dict, List

def speed_ramp_jsx(var: str, source_dur: float, ramps: List[Dict[str, float]], offset: float = 0.0, source_in: float = 0.0) -> str:
    lines = [f'    var _tr_{var} = {var}.property("ADBE Time Remapping");', f'    {var}.timeRemapEnabled = true;']
    for ramp in ramps:
        t = float(ramp.get("t", 0.0)); v = float(ramp.get("v", ramp.get("speed", 1.0)))
        lines.append(f'    _tr_{var}.setValueAtTime({offset+t:.3f}, {source_in+t*v:.3f});')
    return "\n".join(lines)
