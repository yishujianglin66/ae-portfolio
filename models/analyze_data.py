import json
import os

import numpy as np

data_path = os.path.join('models', 'output', 'param-optimizer', 'data', 'train_data.npy')
train_data = np.load(data_path, allow_pickle=True)

print(f'Total samples: {len(train_data)}')
print(f'Sample keys: {list(train_data[0].keys())}')
print(f'Input shape: {train_data[0]["input"].shape}')
print(f'Output shape: {train_data[0]["output"].shape}')

inputs = np.array([s['input'] for s in train_data])
outputs = np.array([s['output'] for s in train_data])

print('\nInput statistics:')
print(f'  Mean: {inputs.mean():.4f}')
print(f'  Std: {inputs.std():.4f}')
print(f'  Min: {inputs.min():.4f}')
print(f'  Max: {inputs.max():.4f}')

print('\nOutput statistics:')
print(f'  Mean: {outputs.mean():.4f}')
print(f'  Std: {outputs.std():.4f}')
print(f'  Min: {outputs.min():.4f}')
print(f'  Max: {outputs.max():.4f}')

if outputs.shape[1] > 1:
    corr_matrix = np.corrcoef(outputs.T)
    upper_tri = corr_matrix[np.triu_indices(corr_matrix.shape[0], k=1)]
    print(f'\nOutput correlation (mean): {upper_tri.mean():.4f}')

style_counts = {}
for s in train_data:
    style = s.get('style', 'unknown')
    style_counts[style] = style_counts.get(style, 0) + 1

print('\nStyle distribution:')
for style, count in sorted(style_counts.items(), key=lambda x: -x[1])[:10]:
    print(f'  {style}: {count}')

effect_counts = {}
for s in train_data:
    effect = s.get('effect_type', 'unknown')
    effect_counts[effect] = effect_counts.get(effect, 0) + 1

print('\nEffect distribution:')
for effect, count in sorted(effect_counts.items(), key=lambda x: -x[1])[:10]:
    print(f'  {effect}: {count}')

print('\nSample output values:')
for i in range(min(3, len(train_data))):
    print(f'  Sample {i}: {outputs[i]}')
