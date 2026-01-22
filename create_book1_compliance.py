#!/usr/bin/env python3
"""
Create final compliance report for Book 1 tanks.
"""

import pandas as pd
import json
from pathlib import Path

def determine_compliance(asdppu, asdbpu, capacity, distance_to_boundary=None):
    """Determine compliance status based on HUD distances."""

    # Convert to float if string
    try:
        asdppu_val = float(asdppu) if asdppu else 0
        asdbpu_val = float(asdbpu) if asdbpu else 0
        capacity_val = float(capacity) if capacity else 0
    except:
        return "Review Required", "Unable to parse distances"

    # Basic compliance rules (can be customized)
    # These are example thresholds - adjust based on actual regulations
    if capacity_val < 100:
        # Small tanks have minimal requirements
        if asdppu_val < 50:
            return "Compliant", "Small volume, minimal distance requirement"
        else:
            return "Review", "Check small tank placement"

    elif capacity_val < 1000:
        # Medium tanks
        if asdppu_val < 200:
            return "Compliant", "Medium tank within safe distance"
        elif asdppu_val < 300:
            return "Review", "Medium tank near threshold"
        else:
            return "Non-Compliant", "Medium tank exceeds safe distance"

    else:
        # Large tanks (>1000 gallons)
        if asdppu_val < 500:
            return "Compliant", "Large tank within safe distance"
        elif asdppu_val < 750:
            return "Review", "Large tank near threshold"
        else:
            return "Non-Compliant", "Large tank exceeds safe distance"

def create_compliance_report(excel_path: str, output_path: str):
    """Create comprehensive compliance report."""

    print(f"📊 Creating compliance report from: {excel_path}")
    df = pd.read_excel(excel_path)

    # Add compliance columns
    df['Compliance Status'] = None
    df['Compliance Notes'] = None
    df['Risk Level'] = None
    df['Action Required'] = None

    # Process each tank
    compliant = 0
    non_compliant = 0
    review = 0

    for idx, row in df.iterrows():
        # Get values
        asdppu = row.get('ASDPPU')
        asdbpu = row.get('ASDBPU')
        capacity = row.get('Capacity (gallons)', 0)

        # Determine compliance
        status, notes = determine_compliance(asdppu, asdbpu, capacity)
        df.at[idx, 'Compliance Status'] = status
        df.at[idx, 'Compliance Notes'] = notes

        # Set risk level
        if status == "Compliant":
            df.at[idx, 'Risk Level'] = "Low"
            df.at[idx, 'Action Required'] = "None - Continue monitoring"
            compliant += 1
        elif status == "Review":
            df.at[idx, 'Risk Level'] = "Medium"
            df.at[idx, 'Action Required'] = "Review placement and verify distances"
            review += 1
        else:
            df.at[idx, 'Risk Level'] = "High"
            df.at[idx, 'Action Required'] = "Immediate review required"
            non_compliant += 1

    # Sort by risk level (High -> Medium -> Low)
    risk_order = {'High': 1, 'Medium': 2, 'Low': 3}
    df['Risk_Sort'] = df['Risk Level'].map(risk_order)
    df = df.sort_values('Risk_Sort').drop('Risk_Sort', axis=1)

    # Save compliance report
    df.to_excel(output_path, index=False)

    # Create summary sheet
    summary_data = {
        'Metric': [
            'Total Tanks',
            'Compliant',
            'Non-Compliant',
            'Review Required',
            'Total Capacity (gallons)',
            'Average ASDPPU (ft)',
            'Average ASDBPU (ft)'
        ],
        'Value': [
            len(df),
            compliant,
            non_compliant,
            review,
            f"{df['Capacity (gallons)'].sum():,.0f}",
            f"{df['ASDPPU'].apply(lambda x: float(x) if x else 0).mean():.2f}",
            f"{df['ASDBPU'].apply(lambda x: float(x) if x else 0).mean():.2f}"
        ]
    }

    summary_df = pd.DataFrame(summary_data)

    # Save with summary sheet
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        df.to_excel(writer, sheet_name='Tank Compliance', index=False)

    print(f"\n✅ Compliance Report Generated")
    print(f"   Total Tanks: {len(df)}")
    print(f"   ✓ Compliant: {compliant}")
    print(f"   ⚠ Review Required: {review}")
    print(f"   ✗ Non-Compliant: {non_compliant}")
    print(f"💾 Saved to: {output_path}")

    # Show high-risk tanks
    high_risk = df[df['Risk Level'] == 'High']
    if len(high_risk) > 0:
        print("\n⚠️ High Risk Tanks:")
        for _, row in high_risk.iterrows():
            print(f"   - {row['Tank ID']}: {row['Capacity (gallons)']} gal, ASDPPU={row['ASDPPU']} ft")

    return df

if __name__ == "__main__":
    # Create compliance report
    compliance_df = create_compliance_report(
        excel_path="book1_with_hud_results.xlsx",
        output_path="book1_final_compliance.xlsx"
    )

    print("\n✨ Compliance report complete!")