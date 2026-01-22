#!/usr/bin/env python3
"""
Deterministic volume calculation module for tank dimensions.
Ensures accurate and consistent volume computations from various units.
"""

from typing import Dict, Optional, List, Tuple
import math


class VolumeCalculator:
    """Dedicated volume computation logic with unit conversions"""
    
    # Conversion factors to feet
    CONVERSIONS_TO_FEET = {
        # Imperial
        'ft': 1.0, 'feet': 1.0, 'foot': 1.0, "'": 1.0,
        'in': 1/12, 'inch': 1/12, 'inches': 1/12, '"': 1/12,
        'yd': 3.0, 'yard': 3.0, 'yards': 3.0,
        'mi': 5280.0, 'mile': 5280.0, 'miles': 5280.0,
        
        # Metric
        'm': 3.28084, 'meter': 3.28084, 'meters': 3.28084, 'metre': 3.28084, 'metros': 3.28084,
        'cm': 0.0328084, 'centimeter': 0.0328084, 'centimeters': 0.0328084, 'centimetros': 0.0328084,
        'mm': 0.000328084, 'millimeter': 0.000328084, 'millimeters': 0.000328084,
        'km': 3280.84, 'kilometer': 3280.84, 'kilometers': 3280.84,
        
        # Spanish variations
        'pies': 1.0, 'pie': 1.0,
        'pulgadas': 1/12, 'pulgada': 1/12,
        'yardas': 3.0, 'yarda': 3.0,
    }
    
    # Volume conversion factors to US gallons
    VOLUME_CONVERSIONS = {
        'gal': 1.0, 'gallon': 1.0, 'gallons': 1.0, 'galones': 1.0, 'galon': 1.0,
        'l': 0.264172, 'liter': 0.264172, 'liters': 0.264172, 'litre': 0.264172, 'litros': 0.264172,
        'ml': 0.000264172, 'milliliter': 0.000264172, 'milliliters': 0.000264172,
        'bbl': 42.0, 'barrel': 42.0, 'barrels': 42.0, 'barriles': 42.0,
        'ft3': 7.48052, 'cubic_feet': 7.48052, 'cu_ft': 7.48052, 'cuft': 7.48052,
        'm3': 264.172, 'cubic_meter': 264.172, 'cubic_meters': 264.172, 'cu_m': 264.172,
        'imperial_gal': 1.20095, 'uk_gal': 1.20095, 'imp_gal': 1.20095,
    }
    
    # Constants
    CUBIC_FEET_TO_GALLONS = 7.48052
    
    def __init__(self, debug: bool = False):
        """Initialize calculator with optional debug mode"""
        self.debug = debug
        self.calculation_log = []
    
    def compute_from_dimensions(
        self, 
        dimensions: Dict,
        validate: bool = True
    ) -> Optional[float]:
        """
        Compute volume in gallons from dimensions dictionary.
        
        Args:
            dimensions: Dict with 'length', 'width', 'height', and 'unit' keys
            validate: Whether to validate reasonable dimensions
            
        Returns:
            Volume in US gallons or None if invalid
        """
        
        try:
            # Extract dimensions
            L = self._extract_number(dimensions.get('length', 0))
            W = self._extract_number(dimensions.get('width', 0))
            H = self._extract_number(dimensions.get('height', 0))
            unit = str(dimensions.get('unit', 'ft')).lower().strip()
            
            if self.debug:
                print(f"📏 Extracted: L={L}, W={W}, H={H}, unit={unit}")
            
            # Validate positive dimensions
            if L <= 0 or W <= 0 or H <= 0:
                if self.debug:
                    print(f"❌ Invalid dimensions: {L}×{W}×{H}")
                return None
            
            # Convert to feet
            factor = self.CONVERSIONS_TO_FEET.get(unit, 1.0)
            if unit not in self.CONVERSIONS_TO_FEET:
                if self.debug:
                    print(f"⚠️ Unknown unit '{unit}', defaulting to feet")
            
            L_ft = L * factor
            W_ft = W * factor
            H_ft = H * factor
            
            if self.debug:
                print(f"📐 In feet: {L_ft:.2f}×{W_ft:.2f}×{H_ft:.2f} ft")
            
            # Validate reasonable dimensions (0.1 to 1000 ft per dimension)
            if validate:
                if not all(0.1 <= dim <= 1000 for dim in [L_ft, W_ft, H_ft]):
                    if self.debug:
                        print(f"⚠️ Dimensions out of reasonable range")
                    return None
            
            # Calculate volume
            volume_cubic_feet = L_ft * W_ft * H_ft
            volume_gallons = volume_cubic_feet * self.CUBIC_FEET_TO_GALLONS
            
            if self.debug:
                print(f"📊 Volume: {volume_cubic_feet:.2f} ft³ = {volume_gallons:.2f} gallons")
            
            # Sanity check volume (0.1 to 1M gallons)
            if validate:
                if not (0.1 <= volume_gallons <= 1_000_000):
                    if self.debug:
                        print(f"⚠️ Volume {volume_gallons:.2f} gallons out of reasonable range")
                    return None
            
            # Log calculation
            self.calculation_log.append({
                'input': dimensions,
                'feet': (L_ft, W_ft, H_ft),
                'volume_ft3': volume_cubic_feet,
                'volume_gal': volume_gallons
            })
            
            return round(volume_gallons, 2)
            
        except (ValueError, TypeError) as e:
            if self.debug:
                print(f"❌ Error computing volume: {e}")
            return None
    
    def compute_from_tuple(
        self, 
        length: float, 
        width: float, 
        height: float, 
        unit: str = 'ft'
    ) -> Optional[float]:
        """
        Compute volume from individual dimension values.
        
        Args:
            length, width, height: Dimension values
            unit: Unit of measurement
            
        Returns:
            Volume in US gallons
        """
        return self.compute_from_dimensions({
            'length': length,
            'width': width,
            'height': height,
            'unit': unit
        })
    
    def parse_direct_volume(self, value: any, unit: str = None) -> Optional[float]:
        """
        Parse a direct volume value with optional unit.
        
        Args:
            value: Volume value (string or number)
            unit: Unit of volume (optional)
            
        Returns:
            Volume in US gallons
        """
        try:
            # Extract number
            volume = self._extract_number(value)
            if volume <= 0:
                return None
            
            # Apply unit conversion if specified
            if unit:
                unit = str(unit).lower().strip()
                factor = self.VOLUME_CONVERSIONS.get(unit, 1.0)
                if unit not in self.VOLUME_CONVERSIONS and self.debug:
                    print(f"⚠️ Unknown volume unit '{unit}', assuming gallons")
                volume = volume * factor
            
            return round(volume, 2)
            
        except (ValueError, TypeError):
            return None
    
    def parse_dimension_string(self, dim_string: str) -> Optional[Dict]:
        """
        Parse dimension string like '10ft x 8ft x 6ft' or 'Length 4m, Width 3m, Height 2m'.
        
        Args:
            dim_string: String containing dimensions
            
        Returns:
            Dictionary with parsed dimensions or None
        """
        import re
        
        if not dim_string:
            return None
        
        dim_string = str(dim_string).lower()
        
        # Pattern 1: "L x W x H unit" (e.g., "10 x 8 x 6 ft")
        pattern1 = r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*([a-z]+)?'
        match1 = re.search(pattern1, dim_string)
        if match1:
            L, W, H = float(match1.group(1)), float(match1.group(2)), float(match1.group(3))
            unit = match1.group(4) or 'ft'
            return {'length': L, 'width': W, 'height': H, 'unit': unit}
        
        # Pattern 2: "Length L unit ; Width W unit ; Height H unit"
        pattern2 = r'(?:length|largo|l)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?.*?(?:width|ancho|w)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?.*?(?:height|alto|altura|h)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*([a-z]+)?'
        match2 = re.search(pattern2, dim_string)
        if match2:
            L = float(match2.group(1))
            W = float(match2.group(3))
            H = float(match2.group(5))
            unit = match2.group(2) or match2.group(4) or match2.group(6) or 'ft'
            return {'length': L, 'width': W, 'height': H, 'unit': unit}
        
        # Pattern 3: "L unit x W unit x H unit" with units after each number
        pattern3 = r'(\d+(?:\.\d+)?)\s*([a-z]+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*([a-z]+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*([a-z]+)'
        match3 = re.search(pattern3, dim_string)
        if match3:
            L = float(match3.group(1))
            W = float(match3.group(3))
            H = float(match3.group(5))
            # Use first unit found (assume all same)
            unit = match3.group(2)
            return {'length': L, 'width': W, 'height': H, 'unit': unit}
        
        return None
    
    def _extract_number(self, value: any) -> float:
        """Extract numeric value from various formats"""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove common non-numeric characters
            cleaned = value.replace(',', '').replace('$', '').strip()
            # Extract first number found
            import re
            match = re.search(r'-?\d+(?:\.\d+)?', cleaned)
            if match:
                return float(match.group())
        
        return 0.0
    
    def validate_tank_volume(
        self, 
        tank: Dict,
        auto_correct: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate tank volume against dimensions if available.
        
        Args:
            tank: Tank dictionary with volume and optional dimensions
            auto_correct: Whether to correct volume if wrong
            
        Returns:
            (is_valid, error_message)
        """
        
        volume = tank.get('volume', 0)
        
        # Check if we have dimensions to validate against
        if tank.get('rect_dims_ft') and len(tank.get('rect_dims_ft', [])) == 3:
            L, W, H = tank['rect_dims_ft']
            expected_volume = self.compute_from_tuple(L, W, H, 'ft')
            
            if expected_volume:
                error_margin = abs(volume - expected_volume) / expected_volume
                
                if error_margin > 0.1:  # 10% tolerance
                    error_msg = f"Volume mismatch: {volume} vs expected {expected_volume:.2f} gallons"
                    
                    if auto_correct:
                        tank['volume'] = expected_volume
                        tank['volume_corrected'] = True
                        tank['volume_source'] = 'computed_from_dimensions'
                        return True, f"Corrected: {error_msg}"
                    
                    return False, error_msg
        
        # Basic range validation
        if volume <= 0:
            return False, "Volume must be positive"
        
        if volume > 1_000_000:
            return False, f"Volume {volume} gallons exceeds reasonable maximum"
        
        return True, None
    
    def get_calculation_summary(self) -> Dict:
        """Get summary of all calculations performed"""
        return {
            'total_calculations': len(self.calculation_log),
            'calculations': self.calculation_log[-10:],  # Last 10
            'units_encountered': list(set(
                log['input'].get('unit', 'unknown') 
                for log in self.calculation_log
            ))
        }


def test_volume_calculator():
    """Test suite for VolumeCalculator"""
    
    calc = VolumeCalculator(debug=True)
    
    test_cases = [
        # (dimensions, expected_gallons, description)
        (
            {"length": 10, "width": 8, "height": 8, "unit": "ft"},
            4787.53,
            "Basic feet calculation"
        ),
        (
            {"length": 120, "width": 96, "height": 60, "unit": "in"},
            2992.21,
            "Inches to gallons"
        ),
        (
            {"length": 4, "width": 3, "height": 2, "unit": "m"},
            6340.13,
            "Meters to gallons"
        ),
        (
            {"length": 400, "width": 300, "height": 200, "unit": "cm"},
            6340.13,
            "Centimeters to gallons"
        ),
        (
            {"length": 4, "width": 3.5, "height": 5, "unit": "ft"},
            523.64,
            "Test case from actual data"
        ),
        (
            {"length": 15, "width": 12, "height": 10, "unit": "ft"},
            13464.94,
            "Larger tank test"
        ),
    ]
    
    print("\n" + "="*60)
    print("VOLUME CALCULATOR TEST SUITE")
    print("="*60 + "\n")
    
    passed = 0
    failed = 0
    
    for dims, expected, description in test_cases:
        result = calc.compute_from_dimensions(dims)
        
        if result is None:
            print(f"❌ FAILED: {description}")
            print(f"   Input: {dims}")
            print(f"   Expected: {expected:.2f} gal, Got: None\n")
            failed += 1
            continue
        
        error_percent = abs(result - expected) / expected * 100
        
        if error_percent < 0.1:  # 0.1% tolerance
            print(f"✅ PASSED: {description}")
            print(f"   {dims['length']}×{dims['width']}×{dims['height']} {dims['unit']} = {result:.2f} gal")
            print(f"   (Expected: {expected:.2f}, Error: {error_percent:.4f}%)\n")
            passed += 1
        else:
            print(f"❌ FAILED: {description}")
            print(f"   Input: {dims}")
            print(f"   Expected: {expected:.2f} gal, Got: {result:.2f} gal")
            print(f"   Error: {error_percent:.2f}%\n")
            failed += 1
    
    # Test dimension string parsing
    print("\n" + "-"*60)
    print("DIMENSION STRING PARSING TESTS")
    print("-"*60 + "\n")
    
    parse_tests = [
        ("10ft x 8ft x 6ft", {"length": 10, "width": 8, "height": 6, "unit": "ft"}),
        ("Length 4 m ; Width 3 m ; Height 2 m", {"length": 4, "width": 3, "height": 2, "unit": "m"}),
        ("120in x 96in x 60in", {"length": 120, "width": 96, "height": 60, "unit": "in"}),
        ("15 x 12 x 10 feet", {"length": 15, "width": 12, "height": 10, "unit": "feet"}),
    ]
    
    for input_str, expected in parse_tests:
        result = calc.parse_dimension_string(input_str)
        if result == expected:
            print(f"✅ Parsed: '{input_str}'")
            print(f"   Result: {result}\n")
            passed += 1
        else:
            print(f"❌ Failed to parse: '{input_str}'")
            print(f"   Expected: {expected}")
            print(f"   Got: {result}\n")
            failed += 1
    
    print("\n" + "="*60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")
    print("="*60)
    
    return passed, failed


if __name__ == "__main__":
    test_volume_calculator()