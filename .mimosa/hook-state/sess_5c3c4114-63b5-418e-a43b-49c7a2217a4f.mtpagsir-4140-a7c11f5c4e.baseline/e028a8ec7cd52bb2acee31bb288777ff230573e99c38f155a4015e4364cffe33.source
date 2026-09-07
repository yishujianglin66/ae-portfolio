from core.composition_tree import CompositionTree, LayerSpec
from core.layer_builders import LayerBuildContext, build_particle_layer


def test_particle_carrier_preserves_layer_window():
    tree = CompositionTree(comp_name="test", style_card="edit", duration=2.0)
    layer = LayerSpec(
        id="particle",
        type="particle",
        name="Particle",
        z_index=1,
        time_range=[0.5, 2.0],
        content={"template": "spark", "t_hit": 1.0},
    )
    jsx = "\n".join(build_particle_layer(LayerBuildContext(tree, [], []), layer))
    assert "layer1.blendingMode = BlendingMode.ADD" in jsx
    assert "layer1.startTime = 0.5" in jsx
    assert "layer1.outPoint = 2.0" in jsx
