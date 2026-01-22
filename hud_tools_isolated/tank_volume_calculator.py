#!/usr/bin/env python3
"""
Tank Volume Calculator - Convert dimensions to gallons
Supports multiple tank shapes and measurement units
"""

import math
import pandas as pd

class TankVolumeCalculator:
    """Calculate tank volumes in gallons from various dimensions"""
    
    # Conversion factors to cubic feet
    CUBIC_INCHES_TO_CUBIC_FEET = 1 / 1728  # 1728 cubic inches = 1 cubic foot
    CUBIC_FEET_TO_GALLONS = 7.48052  # 1 cubic foot = 7.48052 gallons
    CUBIC_INCHES_TO_GALLONS = 0.004329  # 1 cubic inch = 0.004329 gallons
    
    @staticmethod
    def rectangular_tank(length, width, height, unit='feet'):
        """
        Calculate volume of rectangular/cubic tank
        Args:
            length, width, height: dimensions
            unit: 'feet' or 'inches'
        Returns:
            volume in gallons
        """
        volume_cubic = length * width * height
        
        if unit.lower() == 'inches':
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_INCHES_TO_GALLONS
        else:  # feet
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_FEET_TO_GALLONS
            
        return round(gallons, 2)
    
    @staticmethod
    def cylindrical_tank_horizontal(diameter, length, unit='feet'):
        """
        Calculate volume of horizontal cylindrical tank
        Args:
            diameter: tank diameter
            length: tank length
            unit: 'feet' or 'inches'
        Returns:
            volume in gallons
        """
        radius = diameter / 2
        volume_cubic = math.pi * radius * radius * length
        
        if unit.lower() == 'inches':
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_INCHES_TO_GALLONS
        else:  # feet
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_FEET_TO_GALLONS
            
        return round(gallons, 2)
    
    @staticmethod
    def cylindrical_tank_vertical(diameter, height, unit='feet'):
        """
        Calculate volume of vertical cylindrical tank
        Args:
            diameter: tank diameter
            height: tank height
            unit: 'feet' or 'inches'
        Returns:
            volume in gallons
        """
        # Same formula as horizontal, just different orientation
        return TankVolumeCalculator.cylindrical_tank_horizontal(diameter, height, unit)
    
    @staticmethod
    def oval_tank(length, width, height, unit='feet'):
        """
        Calculate volume of oval/elliptical tank
        Args:
            length: major axis
            width: minor axis
            height: tank height
            unit: 'feet' or 'inches'
        Returns:
            volume in gallons
        """
        # Oval area = π × (length/2) × (width/2)
        area = math.pi * (length/2) * (width/2)
        volume_cubic = area * height
        
        if unit.lower() == 'inches':
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_INCHES_TO_GALLONS
        else:  # feet
            gallons = volume_cubic * TankVolumeCalculator.CUBIC_FEET_TO_GALLONS
            
        return round(gallons, 2)
    
    @staticmethod
    def convert_dimensions(value, from_unit, to_unit):
        """Convert between feet and inches"""
        if from_unit == to_unit:
            return value
        elif from_unit == 'feet' and to_unit == 'inches':
            return value * 12
        elif from_unit == 'inches' and to_unit == 'feet':
            return value / 12
        else:
            raise ValueError(f"Unknown conversion: {from_unit} to {to_unit}")

def main():
    print("=" * 70)
    print("TANK VOLUME CALCULATOR - Dimensions to Gallons")
    print("=" * 70)
    
    calc = TankVolumeCalculator()
    
    # Example: Generador tiendita caserio (5.5' x 3.5' x 4')
    print("\n📏 EXAMPLE CALCULATION:")
    print("-" * 40)
    print("Tank: Generador tiendita caserio")
    print("Dimensions: 5.5' × 3.5' × 4' (rectangular)")
    
    volume = calc.rectangular_tank(5.5, 3.5, 4, 'feet')
    print(f"Volume: {volume} gallons")
    
    # Show different tank shape calculations
    print("\n" + "=" * 70)
    print("TANK SHAPE FORMULAS:")
    print("=" * 70)
    
    print("\n1. RECTANGULAR/CUBIC TANK:")
    print("   Volume = Length × Width × Height × 7.48052")
    print("   Example: 6' × 4' × 3' = {:.2f} gallons".format(
        calc.rectangular_tank(6, 4, 3, 'feet')))
    
    print("\n2. CYLINDRICAL TANK (Horizontal or Vertical):")
    print("   Volume = π × (Diameter/2)² × Length × 7.48052")
    print("   Example: 4' diameter × 8' long = {:.2f} gallons".format(
        calc.cylindrical_tank_horizontal(4, 8, 'feet')))
    
    print("\n3. OVAL/ELLIPTICAL TANK:")
    print("   Volume = π × (Length/2) × (Width/2) × Height × 7.48052")
    print("   Example: 6' × 4' × 5' = {:.2f} gallons".format(
        calc.oval_tank(6, 4, 5, 'feet')))
    
    # Conversion table
    print("\n" + "=" * 70)
    print("QUICK REFERENCE - Common Tank Sizes:")
    print("=" * 70)
    
    common_tanks = [
        ("Small Generator", "4' × 2' × 2'", "Rectangular", 
         calc.rectangular_tank(4, 2, 2, 'feet')),
        ("Medium Generator", "5' × 3' × 3'", "Rectangular",
         calc.rectangular_tank(5, 3, 3, 'feet')),
        ("Large Generator", "6' × 4' × 4'", "Rectangular",
         calc.rectangular_tank(6, 4, 4, 'feet')),
        ("Small Cylinder", "3' dia × 4' long", "Cylindrical",
         calc.cylindrical_tank_horizontal(3, 4, 'feet')),
        ("Medium Cylinder", "4' dia × 6' long", "Cylindrical",
         calc.cylindrical_tank_horizontal(4, 6, 'feet')),
        ("Large Cylinder", "5' dia × 8' long", "Cylindrical",
         calc.cylindrical_tank_horizontal(5, 8, 'feet')),
    ]
    
    df = pd.DataFrame(common_tanks, 
                     columns=['Tank Type', 'Dimensions', 'Shape', 'Gallons'])
    print(df.to_string(index=False))
    
    # Interactive calculator
    print("\n" + "=" * 70)
    print("CALCULATE YOUR TANK VOLUME:")
    print("=" * 70)
    print("\nTo calculate a specific tank volume, use these functions:")
    print("\n# Rectangular tank:")
    print("calc.rectangular_tank(length, width, height, 'feet')")
    print("\n# Cylindrical tank:")
    print("calc.cylindrical_tank_horizontal(diameter, length, 'feet')")
    print("\n# Oval tank:")
    print("calc.oval_tank(length, width, height, 'feet')")
    print("\nNote: Use 'inches' instead of 'feet' for inch measurements")
    
    # Save reference guide
    with open('/home/crisipo/Apps/explosivoseval/tank_volume_reference.txt', 'w') as f:
        f.write("TANK VOLUME CONVERSION REFERENCE\n")
        f.write("=" * 50 + "\n\n")
        f.write("CONVERSION FACTORS:\n")
        f.write("• 1 cubic foot = 7.48052 gallons\n")
        f.write("• 1 cubic inch = 0.004329 gallons\n")
        f.write("• 1 foot = 12 inches\n\n")
        f.write("RECTANGULAR TANK FORMULA:\n")
        f.write("Gallons = Length(ft) × Width(ft) × Height(ft) × 7.48052\n\n")
        f.write("CYLINDRICAL TANK FORMULA:\n")
        f.write("Gallons = π × (Diameter(ft)/2)² × Length(ft) × 7.48052\n\n")
        f.write("EXAMPLE CALCULATIONS:\n")
        f.write("-" * 50 + "\n")
        for tank in common_tanks:
            f.write(f"{tank[0]}: {tank[1]} = {tank[3]} gallons\n")
    
    print("\n📁 Reference guide saved to: tank_volume_reference.txt")
    print("=" * 70)

if __name__ == "__main__":
    main()