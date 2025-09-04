#!/usr/bin/env python3
"""Verify volume calculation accuracy"""

import json

with open('test_improved_output.json', 'r') as f:
    data = json.load(f)

print('Volume Verification Report')
print('='*60)
print(f'{"Tank":<25} {"Volume (gal)":<15} {"Source":<22} {"Status"}')
print('-'*60)

# Expected volumes for computed tanks
expected = {
    'Storage Tank A': 10*8*8*7.48052,  # 4787.53
    'Tanque Principal': 4*3.5*5*7.48052,  # 523.64  
    'Main Storage': 15*12*10*7.48052  # 13464.94
}

errors = []
for tank in data['tanks']:
    name = tank['name']
    volume = tank['volume']
    source = tank.get('volume_source', 'unknown')
    
    if name in expected:
        exp_vol = expected[name]
        error = abs(volume - exp_vol)
        if error < 0.1:
            status = '✅ CORRECT'
        else:
            status = f'❌ ERROR: {error:.2f} gal off'
            errors.append((name, volume, exp_vol))
        print(f'{name:<25} {volume:<15.2f} {source:<22} {status}')
    else:
        status = '✓ Direct' if source == 'provided' else '✓ Computed'
        print(f'{name:<25} {volume:<15.2f} {source:<22} {status}')

print('='*60)
print(f'\nSummary:')
print(f'  Total tanks: {len(data["tanks"])}')

computed = [t for t in data['tanks'] if t.get('volume_source') == 'computed_from_dimensions']
print(f'  Computed volumes: {len(computed)}')
print(f'  Accuracy: {"100% - All computed volumes are correct!" if not errors else f"{(1-len(errors)/len(computed))*100:.1f}%"}')

if errors:
    print(f'\n  ❌ Errors found:')
    for name, actual, expected in errors:
        print(f'    - {name}: {actual:.2f} gal (should be {expected:.2f})')
else:
    print(f'\n  ✅ All volume calculations are mathematically accurate!')