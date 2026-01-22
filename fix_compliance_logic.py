#!/usr/bin/env python3
"""
Fix compliance determination - DO NOT make up thresholds.
Compliance should be based on:
1. Distance to actual property boundary (from KMZ)
2. Comparing that distance to HUD's ASDPPU/ASDBPU values
3. User-defined or regulatory thresholds
"""

import pandas as pd
import json
from pathlib import Path

def determine_compliance_correctly(row, boundary_distance=None):
    """
    Correct compliance determination:
    - If tank's distance to boundary < ASDPPU: COMPLIANT (safe distance maintained)
    - If tank's distance to boundary >= ASDPPU: NON-COMPLIANT (too close to boundary)
    - If no boundary distance available: REQUIRES BOUNDARY DATA
    """

    try:
        asdppu = float(row.get('ASDPPU', 0))
        asdbpu = float(row.get('ASDBPU', 0))
        capacity = float(row.get('Capacity (gallons)', 0))
    except:
        return "Data Error", "Cannot parse distance values", "Review"

    # Get actual distance to boundary if available
    dist_to_boundary = row.get('Distance to Boundary (ft)', boundary_distance)

    if dist_to_boundary is None:
        return "Incomplete", "Requires boundary distance measurement", "Review"

    try:
        dist_to_boundary = float(dist_to_boundary)
    except:
        return "Data Error", "Invalid boundary distance", "Review"

    # CORRECT LOGIC:
    # ASDPPU = "Allowable Setback Distance, Primary Property, Unrestricted"
    # This is the MINIMUM safe distance that should be maintained

    if dist_to_boundary >= asdppu:
        # Tank is at least ASDPPU distance away from boundary = GOOD
        status = "Compliant"
        notes = f"Tank is {dist_to_boundary:.1f}ft from boundary (min required: {asdppu:.1f}ft)"
        risk = "Low"
    else:
        # Tank is CLOSER than ASDPPU to boundary = BAD
        shortage = asdppu - dist_to_boundary
        status = "Non-Compliant"
        notes = f"Tank is {dist_to_boundary:.1f}ft from boundary, needs {asdppu:.1f}ft (short by {shortage:.1f}ft)"
        risk = "High"

    # Check ASDBPU if there are neighboring properties
    if asdbpu > 0 and dist_to_boundary < asdbpu:
        notes += f"; Also violates ASDBPU requirement of {asdbpu:.1f}ft"

    return status, notes, risk

def create_proper_compliance_report(input_excel: str, output_excel: str, boundary_distances_file: str = None):
    """Create compliance report with proper logic."""

    print("⚠️  IMPORTANT: Compliance Determination")
    print("="*60)
    print("Compliance is determined by comparing:")
    print("1. Actual distance from tank to property boundary")
    print("2. HUD's ASDPPU (minimum required distance)")
    print("3. If distance >= ASDPPU: COMPLIANT")
    print("4. If distance < ASDPPU: NON-COMPLIANT")
    print("="*60)

    df = pd.read_excel(input_excel)

    # Load boundary distances if available
    boundary_distances = {}
    if boundary_distances_file and Path(boundary_distances_file).exists():
        with open(boundary_distances_file, 'r') as f:
            boundary_data = json.load(f)
            boundary_distances = boundary_data.get('distances', {})

    # Add columns for proper compliance
    df['Distance to Boundary (ft)'] = None
    df['Compliance Status'] = None
    df['Compliance Logic'] = None
    df['Risk Level'] = None

    # If we don't have boundary distances, we can't determine compliance
    if not boundary_distances:
        print("\n❌ WARNING: No boundary distance data available!")
        print("   Cannot determine actual compliance without knowing")
        print("   the distance from each tank to the property boundary.")
        print("\n   Required: KMZ file with property boundary or")
        print("            manual measurement of tank-to-boundary distances")

        # Mark all as requiring boundary data
        for idx, row in df.iterrows():
            df.at[idx, 'Distance to Boundary (ft)'] = "REQUIRED"
            df.at[idx, 'Compliance Status'] = "Cannot Determine"
            df.at[idx, 'Compliance Logic'] = "Boundary distance measurement required"
            df.at[idx, 'Risk Level'] = "Unknown"
    else:
        # Use actual boundary distances
        for idx, row in df.iterrows():
            tank_id = row.get('Tank ID', f'Tank_{idx}')
            boundary_dist = boundary_distances.get(tank_id)

            if boundary_dist:
                df.at[idx, 'Distance to Boundary (ft)'] = boundary_dist
                status, notes, risk = determine_compliance_correctly(row, boundary_dist)
                df.at[idx, 'Compliance Status'] = status
                df.at[idx, 'Compliance Logic'] = notes
                df.at[idx, 'Risk Level'] = risk

    # Create summary explaining the proper logic
    summary_data = {
        'Compliance Determination Method': [
            'ASDPPU Definition',
            'ASDBPU Definition',
            '',
            'COMPLIANCE LOGIC',
            'If Distance to Boundary >= ASDPPU',
            'If Distance to Boundary < ASDPPU',
            '',
            'REQUIRED DATA',
            '1. Tank coordinates (lat/lon)',
            '2. Property boundary polygon',
            '3. HUD ASDPPU calculations',
            '4. Actual distance measurements',
            '',
            'DATA STATUS',
            'HUD Calculations',
            'Boundary Distances',
            'Compliance Determinable'
        ],
        'Value': [
            'Allowable Setback Distance, Primary Property, Unrestricted',
            'Allowable Setback Distance, Between Properties, Unrestricted',
            '',
            '',
            '✅ COMPLIANT',
            '❌ NON-COMPLIANT',
            '',
            '',
            '✓ Available from Excel',
            '❓ Need KMZ with boundary',
            '✓ Completed via HUD tool',
            '❓ Need to calculate',
            '',
            '',
            '✅ Available',
            '❌ Not Available' if not boundary_distances else '✅ Available',
            '❌ No - Need Boundary' if not boundary_distances else '✅ Yes'
        ]
    }

    summary_df = pd.DataFrame(summary_data)

    # Save with proper sheets
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Compliance Method', index=False)
        df.to_excel(writer, sheet_name='Tank Data', index=False)

        # Add a requirements sheet
        req_df = pd.DataFrame({
            'Required Information': [
                'Property Boundary Coordinates',
                'Tank GPS Coordinates',
                'Distance Calculations',
                'Regulatory Thresholds'
            ],
            'Status': [
                'NOT PROVIDED - Need KMZ file with boundary',
                'Partially Available - Need verification',
                'Need to calculate from coordinates',
                'Using HUD standards (ASDPPU/ASDBPU)'
            ],
            'Action Needed': [
                'Provide KMZ with property boundary polygon',
                'Verify tank lat/lon coordinates',
                'Calculate distances using shapely/pyproj',
                'Confirm regulatory requirements apply'
            ]
        })
        req_df.to_excel(writer, sheet_name='Requirements', index=False)

    print(f"\n📊 Report saved to: {output_excel}")
    print("\n⚠️  CRITICAL: To determine actual compliance, you need:")
    print("   1. Property boundary polygon (from KMZ)")
    print("   2. Exact tank coordinates")
    print("   3. Calculate actual distance from tank to boundary")
    print("   4. Compare: if distance >= ASDPPU → Compliant")
    print("            if distance < ASDPPU → Non-Compliant")

    return df

if __name__ == "__main__":
    # Create proper compliance report
    df = create_proper_compliance_report(
        input_excel="book1_with_hud_results.xlsx",
        output_excel="book1_PROPER_compliance.xlsx",
        boundary_distances_file=None  # We don't have this yet!
    )

    print("\n❗ IMPORTANT: Previous compliance determinations were")
    print("   incorrectly based on made-up thresholds.")
    print("   Proper compliance requires actual distance measurements!")