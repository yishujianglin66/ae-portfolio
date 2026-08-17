from .composition_tree import LayerSpec
def pick_fx_layer(category, t_hit, duration=0.5, seed=0, z_index=0):
    return LayerSpec(id=f'fx_{category}_{seed}', type='solid', name=f'FX {category}', z_index=z_index, time_range=[max(0,t_hit-duration/2),t_hit+duration/2], content={'color':[255,255,255], 'category':category, 'opacity':80})
