#!/usr/bin/env python3
"""
Simple JSON validator for tank configurations
"""

import json
import sys
from pathlib import Path

def validate_tank_json(file_path):
    """Validate tank configuration JSON file"""
    
    print(f"🔍 Validating: {file_path}\n")
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON format: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    
    errors = []
    warnings = []
    
    # Check required top-level fields
    if 'tanks' not in data:
        errors.append("Missing required 'tanks' field")
        return False
    
    if not isinstance(data['tanks'], list):
        errors.append("'tanks' must be an array")
        return False
    
    # Validate each tank
    tank_ids = set()
    for i, tank in enumerate(data['tanks']):
        tank_num = i + 1
        
        # Check required fields
        required = ['id', 'name', 'volume', 'type', 'has_dike']
        for field in required:
            if field not in tank:
                errors.append(f"Tank {tank_num}: Missing required field '{field}'")
        
        # Check ID uniqueness
        if 'id' in tank:
            if tank['id'] in tank_ids:
                errors.append(f"Tank {tank_num}: Duplicate ID {tank['id']}")
            tank_ids.add(tank['id'])
        
        # Validate types
        if 'volume' in tank:
            if not isinstance(tank['volume'], (int, float)) or tank['volume'] < 0:
                errors.append(f"Tank {tank_num}: Invalid volume (must be positive number)")
            elif tank['volume'] == 0:
                warnings.append(f"Tank {tank_num} ({tank.get('name', 'unnamed')}): Volume is 0")
        
        if 'type' in tank:
            valid_types = ['diesel', 'fuel', 'pressurized_gas', 'lpg', 'gasoline']
            if tank['type'] not in valid_types:
                errors.append(f"Tank {tank_num}: Invalid type '{tank['type']}' (valid: {', '.join(valid_types)})")
        
        if 'has_dike' in tank:
            if not isinstance(tank['has_dike'], bool):
                errors.append(f"Tank {tank_num}: 'has_dike' must be boolean")
            
            # Check dike dimensions consistency
            if tank['has_dike'] and 'dike_dims' not in tank:
                warnings.append(f"Tank {tank_num} ({tank.get('name', 'unnamed')}): Has dike but missing dimensions")
            elif not tank['has_dike'] and 'dike_dims' in tank:
                warnings.append(f"Tank {tank_num} ({tank.get('name', 'unnamed')}): Has dike dimensions but has_dike is false")
        
        if 'dike_dims' in tank:
            if not isinstance(tank['dike_dims'], list) or len(tank['dike_dims']) != 2:
                errors.append(f"Tank {tank_num}: 'dike_dims' must be array with 2 numbers [length, width]")
    
    # Print results
    if errors:
        print("❌ VALIDATION FAILED\n")
        print("Errors:")
        for error in errors:
            print(f"  • {error}")
    else:
        print("✅ VALIDATION PASSED\n")
        
        print(f"Summary:")
        print(f"  • Total tanks: {len(data['tanks'])}")
        
        # Type distribution
        type_counts = {}
        for tank in data['tanks']:
            t = tank.get('type', 'unknown')
            type_counts[t] = type_counts.get(t, 0) + 1
        
        print(f"  • Tank types:")
        for t, count in type_counts.items():
            print(f"      - {t}: {count}")
        
        # Dike count
        dike_count = sum(1 for t in data['tanks'] if t.get('has_dike', False))
        print(f"  • Tanks with dikes: {dike_count}")
    
    if warnings:
        print(f"\n⚠ Warnings:")
        for warning in warnings:
            print(f"  • {warning}")
    
    return len(errors) == 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_tank_json.py <json_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    if validate_tank_json(file_path):
        sys.exit(0)
    else:
        sys.exit(1)