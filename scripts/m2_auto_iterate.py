from pathlib import Path
from core.synthesis_orchestrator import SynthesisOrchestrator

def render_tree(tree, out_mp4, aep_name='project.aep', lut=None):
    result=SynthesisOrchestrator().execute(tree, dry_run=True)
    if result.get('status') != 'dry_run': return False
    out=Path(out_mp4); out.parent.mkdir(parents=True,exist_ok=True)
    out.with_suffix('.jsx').write_text(result['jsx'],encoding='utf-8')
    out.with_suffix('.aep.json').write_text('{"status":"dry_run"}',encoding='utf-8')
    return False
