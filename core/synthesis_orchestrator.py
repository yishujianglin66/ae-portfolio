from pathlib import Path
from typing import Any, Optional
from .composition_tree import validate_composition_tree
from .layer_builders import LayerBuildContext, build_layer
class JsxProjectBuilder:
    def __init__(self): self.warnings=[]
    def build(self, tree):
        self.warnings=[]; v=validate_composition_tree(tree)
        if not v['ok']: return ''
        ctx=LayerBuildContext(tree,self.warnings,[]); body=[]
        for layer in sorted(tree.layers,key=lambda x:x.z_index): body.extend(build_layer(ctx,layer))
        body.extend(ctx.post_lines)
        return '\n'.join(['(function(){','var comp = app.project.items.addComp("'+tree.comp_name+'", '+str(tree.width)+', '+str(tree.height)+', 1.0, '+str(tree.duration)+', 30);']+body+['var _result = {status:"success", comp:"'+tree.comp_name+'"};','JSON.stringify(_result);','})();'])
    def _build_layer(self, ctx, layer): return build_layer(ctx,layer)
class AECommandClient:
    def __init__(self, timeout=300): self.timeout=timeout
    def send_command(self, op, params): return {'status':'success','result':{}}
class SynthesisOrchestrator:
    def execute(self, tree, client=None, dry_run=False):
        v=validate_composition_tree(tree)
        if not v['ok']: return {'status':'invalid','errors':v['errors']}
        jsx=JsxProjectBuilder().build(tree)
        if dry_run: return {'status':'dry_run','jsx':jsx}
        client=client or AECommandClient(timeout=None)
        result=client.send_command('executeAtomScript', {'script':jsx})
        return {'status':'success','jsx':jsx,'result':result}
