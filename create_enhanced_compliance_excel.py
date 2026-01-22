#!/usr/bin/env python3
"""
Create enhanced compliance Excel with both ASDPPU and ASDBPU prominently displayed.
"""

import pandas as pd
from pathlib import Path

def determine_compliance_enhanced(asdppu, asdbpu, capacity):
    """Enhanced compliance determination using both distances."""

    try:
        asdppu_val = float(asdppu) if asdppu else 0
        asdbpu_val = float(asdbpu) if asdbpu else 0
        capacity_val = float(capacity) if capacity else 0
    except:
        return "Review Required", "Unable to parse distances", "Unknown"

    # Compliance based on both distances
    compliance_status = "Compliant"
    notes = []
    risk = "Low"

    # Check ASDPPU (Primary Property Line)
    if capacity_val >= 10000:  # Large tanks
        if asdppu_val > 800:
            compliance_status = "Non-Compliant"
            notes.append(f"ASDPPU {asdppu_val:.0f}ft exceeds 800ft for large tank")
            risk = "High"
        elif asdppu_val > 600:
            compliance_status = "Review"
            notes.append(f"ASDPPU {asdppu_val:.0f}ft approaching limit")
            risk = "Medium"
    elif capacity_val >= 1000:  # Medium tanks
        if asdppu_val > 500:
            compliance_status = "Non-Compliant"
            notes.append(f"ASDPPU {asdppu_val:.0f}ft exceeds 500ft for medium tank")
            risk = "High"
        elif asdppu_val > 350:
            if compliance_status == "Compliant":
                compliance_status = "Review"
            notes.append(f"ASDPPU {asdppu_val:.0f}ft approaching limit")
            if risk == "Low":
                risk = "Medium"

    # Check ASDBPU (Between Properties)
    if asdbpu_val > asdppu_val * 0.3:  # If ASDBPU is more than 30% of ASDPPU
        if compliance_status == "Compliant":
            compliance_status = "Review"
        notes.append(f"ASDBPU ratio high ({asdbpu_val:.0f}ft)")
        if risk == "Low":
            risk = "Medium"

    # Combine notes
    if not notes:
        notes = ["Within acceptable limits for both distances"]

    return compliance_status, "; ".join(notes), risk

def create_enhanced_compliance_excel(input_excel: str, output_excel: str):
    """Create enhanced Excel with both distances prominently displayed."""

    print(f"📊 Creating enhanced compliance report...")
    df = pd.read_excel(input_excel)

    # Reorder columns to put distances together and prominent
    key_columns = [
        'Tank ID',
        'Tank Use/Description',
        'Capacity (gallons)',
        'ASDPPU',  # Keep both distances together
        'ASDBPU',
        'Location',
        'Secondary Containment',
        'Latitude',
        'Longitude',
        'ASDPNPD',
        'ASDBNPD',
        'Status',
        'Flood Zone',
        'HUD Screenshot'
    ]

    # Reorder columns
    available_cols = [col for col in key_columns if col in df.columns]
    other_cols = [col for col in df.columns if col not in key_columns]
    df = df[available_cols + other_cols]

    # Add enhanced compliance columns
    df['Compliance Status'] = None
    df['Risk Level'] = None
    df['Compliance Notes'] = None
    df['ASDPPU/ASDBPU Ratio'] = None
    df['Action Required'] = None

    # Calculate compliance for each tank
    stats = {'Compliant': 0, 'Non-Compliant': 0, 'Review': 0}

    for idx, row in df.iterrows():
        asdppu = row.get('ASDPPU')
        asdbpu = row.get('ASDBPU')
        capacity = row.get('Capacity (gallons)', 0)

        # Calculate ratio
        try:
            asdppu_val = float(asdppu) if asdppu else 0
            asdbpu_val = float(asdbpu) if asdbpu else 0
            if asdppu_val > 0:
                ratio = asdbpu_val / asdppu_val
                df.at[idx, 'ASDPPU/ASDBPU Ratio'] = f"{ratio:.2%}"
        except:
            df.at[idx, 'ASDPPU/ASDBPU Ratio'] = "N/A"

        # Determine compliance
        status, notes, risk = determine_compliance_enhanced(asdppu, asdbpu, capacity)
        df.at[idx, 'Compliance Status'] = status
        df.at[idx, 'Compliance Notes'] = notes
        df.at[idx, 'Risk Level'] = risk

        # Set action
        if status == "Compliant":
            df.at[idx, 'Action Required'] = "Continue routine monitoring"
            stats['Compliant'] += 1
        elif status == "Review":
            df.at[idx, 'Action Required'] = "Review placement and verify calculations"
            stats['Review'] += 1
        else:
            df.at[idx, 'Action Required'] = "IMMEDIATE: Review required for compliance"
            stats['Non-Compliant'] += 1

    # Sort by risk level
    risk_order = {'High': 1, 'Medium': 2, 'Low': 3}
    df['_sort'] = df['Risk Level'].map(risk_order)
    df = df.sort_values('_sort').drop('_sort', axis=1)

    # Create summary data
    summary_data = {
        'Metric': [
            'Total Tanks Analyzed',
            'Total Capacity (gallons)',
            '',
            'COMPLIANCE STATUS',
            '✅ Compliant',
            '⚠️ Review Required',
            '❌ Non-Compliant',
            '',
            'DISTANCE STATISTICS',
            'Average ASDPPU (ft)',
            'Maximum ASDPPU (ft)',
            'Average ASDBPU (ft)',
            'Maximum ASDBPU (ft)',
            '',
            'RISK DISTRIBUTION',
            'High Risk Tanks',
            'Medium Risk Tanks',
            'Low Risk Tanks'
        ],
        'Value': [
            len(df),
            f"{df['Capacity (gallons)'].sum():,.0f}",
            '',
            '',
            stats['Compliant'],
            stats['Review'],
            stats['Non-Compliant'],
            '',
            '',
            f"{df['ASDPPU'].apply(lambda x: float(x) if x else 0).mean():.2f}",
            f"{df['ASDPPU'].apply(lambda x: float(x) if x else 0).max():.2f}",
            f"{df['ASDBPU'].apply(lambda x: float(x) if x else 0).mean():.2f}",
            f"{df['ASDBPU'].apply(lambda x: float(x) if x else 0).max():.2f}",
            '',
            '',
            len(df[df['Risk Level'] == 'High']),
            len(df[df['Risk Level'] == 'Medium']),
            len(df[df['Risk Level'] == 'Low'])
        ]
    }

    summary_df = pd.DataFrame(summary_data)

    # Create distance comparison sheet
    distance_df = df[['Tank ID', 'Capacity (gallons)', 'ASDPPU', 'ASDBPU', 'ASDPPU/ASDBPU Ratio', 'Compliance Status']].copy()

    # Save to Excel with multiple sheets
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary Report', index=False)
        df.to_excel(writer, sheet_name='Full Compliance Data', index=False)
        distance_df.to_excel(writer, sheet_name='Distance Analysis', index=False)

        # Add a high-risk sheet if there are any
        high_risk = df[df['Risk Level'] == 'High']
        if len(high_risk) > 0:
            high_risk[['Tank ID', 'Capacity (gallons)', 'ASDPPU', 'ASDBPU', 'Compliance Notes', 'Action Required']].to_excel(
                writer, sheet_name='High Risk Tanks', index=False
            )

    print(f"\n✅ Enhanced Compliance Report Generated")
    print(f"   Total Tanks: {len(df)}")
    print(f"   ✅ Compliant: {stats['Compliant']}")
    print(f"   ⚠️ Review: {stats['Review']}")
    print(f"   ❌ Non-Compliant: {stats['Non-Compliant']}")
    print(f"\n📊 Distance Summary:")
    print(f"   ASDPPU Range: {df['ASDPPU'].apply(lambda x: float(x) if x else 0).min():.0f} - {df['ASDPPU'].apply(lambda x: float(x) if x else 0).max():.0f} ft")
    print(f"   ASDBPU Range: {df['ASDBPU'].apply(lambda x: float(x) if x else 0).min():.0f} - {df['ASDBPU'].apply(lambda x: float(x) if x else 0).max():.0f} ft")
    print(f"\n💾 Saved to: {output_excel}")

    # Show all tanks with both distances
    print("\n📋 All Tanks with Both Distances:")
    print("="*70)
    for _, row in df.iterrows():
        tank_id = row['Tank ID']
        capacity = row['Capacity (gallons)']
        asdppu = row['ASDPPU']
        asdbpu = row['ASDBPU']
        status = row['Compliance Status']
        print(f"{tank_id:15} {capacity:7.0f} gal | ASDPPU: {asdppu:7} ft | ASDBPU: {asdbpu:7} ft | {status}")

    return df

if __name__ == "__main__":
    # Create enhanced report
    df = create_enhanced_compliance_excel(
        input_excel="book1_with_hud_results.xlsx",
        output_excel="book1_enhanced_compliance.xlsx"
    )

    print("\n✨ Enhanced compliance Excel created with both ASDPPU and ASDBPU!")