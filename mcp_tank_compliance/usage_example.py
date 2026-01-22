#!/usr/bin/env python3
"""
Example usage of Tank Compliance MCP Tools
Shows how an agent would use these tools to process tank compliance assessment
"""

import asyncio
import json
from typing import Dict, Any


class TankComplianceAgent:
    """Example agent using MCP tools for tank compliance"""

    def __init__(self, mcp_client):
        self.mcp = mcp_client

    async def process_tank_compliance_pipeline(self, excel_path: str, kmz_path: str):
        """
        Complete pipeline for tank compliance assessment

        This demonstrates the full workflow using MCP tools
        """
        print("=" * 80)
        print("TANK COMPLIANCE ASSESSMENT PIPELINE")
        print("=" * 80)

        # Step 1: Parse KMZ file to get sites and polygon
        print("\n1. Parsing KMZ file...")
        kmz_data = await self.mcp.call('parse_kmz_file', {
            'kmz_path': kmz_path
        })

        sites_from_kmz = kmz_data['sites']
        polygons = kmz_data['polygons']
        print(f"   Found {len(sites_from_kmz)} sites and {len(polygons)} polygons")

        # Get the site boundary polygon (usually the first one)
        if not polygons:
            print("   ERROR: No polygon boundary found!")
            return

        boundary_polygon = polygons[0]['coordinates']

        # Step 2: Process Excel data
        print("\n2. Processing Excel file...")

        # Example: Parse tank measurements
        measurement_example = "39\"x46\"x229\""
        volume_result = await self.mcp.call('parse_tank_measurements', {
            'measurement_str': measurement_example
        })
        print(f"   Example measurement {measurement_example} = {volume_result['volume_gallons']} gallons")

        # Example: Parse multi-tank capacities
        capacity_example = "1778 gal; 1126 gal"
        capacity_result = await self.mcp.call('parse_multi_tank_capacities', {
            'capacity_str': capacity_example
        })
        print(f"   Example capacity {capacity_example}:")
        print(f"     - Tanks: {capacity_result['tanks']}")
        print(f"     - Largest (for compliance): {capacity_result['largest_capacity']} gal")

        # Step 3: Match sites between Excel and KMZ
        print("\n3. Matching sites between Excel and KMZ...")

        # In real usage, extract these from Excel
        excel_site_names = [
            "CDT Juncos",
            "Coliseo Rafael G Amalbert",
            "Plaza del Nino",
            "PRASA Generador"
        ]

        matching_result = await self.mcp.call('match_sites_fuzzy', {
            'excel_sites': excel_site_names,
            'kmz_sites': sites_from_kmz
        })
        print(f"   Match rate: {matching_result['match_rate']*100:.1f}%")
        print(f"   Matched: {len(matching_result['matches'])}")
        print(f"   Unmatched Excel: {len(matching_result['unmatched_excel'])}")

        # Step 4: Calculate distances for matched sites
        print("\n4. Calculating distances to polygon boundary...")

        # Example for one site
        if matching_result['matches']:
            site_name = list(matching_result['matches'].keys())[0]
            site_coords = matching_result['matches'][site_name]

            distance_result = await self.mcp.call('calculate_distance_to_polygon', {
                'point_lat': site_coords['latitude'],
                'point_lon': site_coords['longitude'],
                'polygon_coords': boundary_polygon
            })

            print(f"   {site_name}:")
            print(f"     - Distance: {distance_result['distance_feet']} ft")
            print(f"     - Location: {distance_result['point_location']}")

        # Step 5: Assess compliance
        print("\n5. Assessing compliance...")

        # Example ASD string
        asd_example = "ASDPPU: 351.50 ft, ASDBPU: 65.61 ft"
        asd_values = await self.mcp.call('extract_asd_values', {
            'asd_string': asd_example
        })
        print(f"   Extracted ASD values: {asd_values}")

        # Assess compliance for the example
        if distance_result:
            compliance_result = await self.mcp.call('assess_compliance', {
                'distance_feet': distance_result['distance_feet'],
                'asd_values': asd_values,
                'has_dike': False
            })

            print(f"   Compliance assessment:")
            print(f"     - Status: {compliance_result['status']}")
            print(f"     - Required: {compliance_result['required_distance']} ft")
            print(f"     - Margin: {compliance_result['margin']} ft")

        # Step 6: Process entire Excel file
        print("\n6. Processing complete Excel file...")

        full_results = await self.mcp.call('process_excel_compliance', {
            'excel_path': excel_path,
            'polygon_coords': boundary_polygon
        })

        summary = full_results['summary']
        print(f"   Results summary:")
        print(f"     - Total sites: {summary['total']}")
        print(f"     - Compliant: {summary['compliant']}")
        print(f"     - Non-compliant: {summary['non_compliant']}")
        print(f"     - No ASD data: {summary['no_asd_data']}")
        print(f"     - No coordinates: {summary['no_coordinates']}")

        # Step 7: Create visualization
        print("\n7. Creating KMZ visualization...")

        # Prepare sites for KMZ
        kmz_sites = []
        for site in full_results['sites']:
            if site.get('latitude') and site.get('longitude'):
                # Determine display name based on tank capacity
                if site.get('tank_capacity'):
                    capacity_parsed = await self.mcp.call('parse_multi_tank_capacities', {
                        'capacity_str': site['tank_capacity']
                    })
                    if capacity_parsed['largest_capacity']:
                        display_name = f"{int(capacity_parsed['largest_capacity'])} gal tank"
                    else:
                        display_name = site['site_name']
                else:
                    display_name = site['site_name']

                kmz_sites.append({
                    'site_name': site['site_name'],
                    'display_name': display_name,
                    'latitude': site['latitude'],
                    'longitude': site['longitude'],
                    'status': site.get('status', 'Unknown'),
                    'distance_feet': site.get('distance_feet'),
                    'margin': site.get('margin')
                })

        kmz_result = await self.mcp.call('create_kmz_file', {
            'sites': kmz_sites,
            'polygons': polygons,
            'output_path': 'tank_compliance_output.kmz'
        })

        print(f"   Created KMZ with {kmz_result['sites_count']} sites")
        print(f"   Output: {kmz_result['path']}")

        # Step 8: Update Excel with results
        print("\n8. Updating Excel with results...")

        update_result = await self.mcp.call('update_excel_with_results', {
            'excel_path': excel_path,
            'results': full_results['sites'],
            'output_path': 'tank_compliance_final.xlsx'
        })

        print(f"   Updated {update_result['rows_updated']} rows")
        print(f"   Output: {update_result['path']}")

        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)

    async def handle_special_cases(self):
        """
        Demonstrate handling special cases
        """
        print("\n" + "=" * 80)
        print("SPECIAL CASE HANDLERS")
        print("=" * 80)

        # Handle DMS to decimal conversion
        print("\n1. Converting DMS coordinates to decimal...")
        decimal_lat = await self.mcp.call('convert_dms_to_decimal', {
            'degrees': 18,
            'minutes': 13,
            'seconds': 44.64,
            'direction': 'N'
        })
        decimal_lon = await self.mcp.call('convert_dms_to_decimal', {
            'degrees': 65,
            'minutes': 55,
            'seconds': 23.48,
            'direction': 'W'
        })
        print(f"   18°13'44.64\"N = {decimal_lat}°")
        print(f"   65°55'23.48\"W = {decimal_lon}°")

        # Handle complex tank measurements
        print("\n2. Parsing complex tank measurements...")

        measurements = [
            "39\"x46\"x229\"",  # Rectangular
            "36\"x34\"x75\"",   # Rectangular with typo
            "48\"x120\"",       # Cylindrical
            "182\"x55\"x26\""   # Large rectangular
        ]

        for meas in measurements:
            result = await self.mcp.call('parse_tank_measurements', {
                'measurement_str': meas
            })
            print(f"   {meas} = {result.get('volume_gallons', 'Error')} gal ({result.get('shape', 'unknown')})")

        # Handle multiple tank scenarios
        print("\n3. Handling sites with multiple tanks...")

        multi_tank_examples = [
            "1778 gal; 1126 gal",
            "358 gal; 399 gal",
            "964.0 gal",
            "500 gal; 300 gal; 200 gal"
        ]

        for example in multi_tank_examples:
            result = await self.mcp.call('parse_multi_tank_capacities', {
                'capacity_str': example
            })
            print(f"   {example}:")
            print(f"     - Number of tanks: {result['number_of_tanks']}")
            print(f"     - Use for compliance: {result['use_for_compliance']} gal")


# Mock MCP client for demonstration
class MockMCPClient:
    """Mock MCP client for testing"""

    def __init__(self):
        from server import TankComplianceTools
        self.tools = TankComplianceTools()

    async def call(self, method: str, params: Dict[str, Any]) -> Any:
        """Mock call to MCP tools"""
        # In real implementation, this would send request to MCP server
        method_map = {
            'parse_tank_measurements': self.tools.parse_tank_measurements,
            'parse_multi_tank_capacities': self.tools.parse_multi_tank_capacities,
            'extract_asd_values': self.tools.extract_asd_values,
            'parse_kmz_file': self.tools.parse_kmz_file,
            'convert_dms_to_decimal': self.tools.convert_dms_to_decimal,
            'match_sites_fuzzy': self.tools.match_sites_fuzzy,
            'calculate_distance_to_polygon': self.tools.calculate_distance_to_polygon,
            'batch_calculate_distances': self.tools.batch_calculate_distances,
            'assess_compliance': self.tools.assess_compliance,
            'process_excel_compliance': self.tools.process_excel_compliance,
            'create_kmz_file': self.tools.create_kmz_file,
            'update_excel_with_results': self.tools.update_excel_with_results
        }

        if method in method_map:
            # Call the method with unpacked parameters
            func = method_map[method]
            if asyncio.iscoroutinefunction(func):
                return await func(**params)
            else:
                return func(**params)
        else:
            raise ValueError(f"Unknown method: {method}")


async def main():
    """Main demonstration"""

    # Create mock MCP client
    mcp_client = MockMCPClient()

    # Create agent
    agent = TankComplianceAgent(mcp_client)

    # Run demonstrations
    print("\n🚀 Tank Compliance MCP Tools Demonstration\n")

    # Demonstrate special case handlers
    await agent.handle_special_cases()

    # Demonstrate full pipeline (commented out as it needs actual files)
    # await agent.process_tank_compliance_pipeline(
    #     'tank_locations.xlsx',
    #     'site_boundary.kmz'
    # )

    print("\n✅ Demonstration complete!")


if __name__ == "__main__":
    asyncio.run(main())