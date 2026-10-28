"""Validate embodiment before downloading or loading a large policy."""
def validate_libero_smol_config(config):
    if config.get('type')!='smolvla':raise ValueError('Expected a SmolVLA checkpoint')
    inputs=config.get('input_features',{});outputs=config.get('output_features',{})
    if inputs.get('observation.state',{}).get('shape')!=[8]:raise ValueError('LIBERO requires 8 state features; smolvla_base has a different embodiment')
    if outputs.get('action',{}).get('shape')!=[7]:raise ValueError('LIBERO requires 7 action features')
    for key in ['observation.images.camera1','observation.images.camera2']:
        if inputs.get(key,{}).get('shape')!=[3,256,256]:raise ValueError(f'Unexpected camera feature: {key}')
