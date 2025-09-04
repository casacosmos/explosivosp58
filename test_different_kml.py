#!/usr/bin/env python3
"""Test KMZ parser with different KML configurations"""

import tempfile
import zipfile
from pathlib import Path
from kmz_parser_agent import KMZParserAgent

# Test Case 1: KML with no namespace issues
simple_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Simple Test</name>
    <Placemark>
      <name>Test Point</name>
      <Point>
        <coordinates>-122.0844,37.4220,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Test Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -122.084,37.422,0
              -122.085,37.422,0
              -122.085,37.423,0
              -122.084,37.423,0
              -122.084,37.422,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

# Test Case 2: KML with different namespaces (like from QGIS)
qgis_style_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>QGIS Export</name>
    <Placemark>
      <name>Building A</name>
      <description>Office Building</description>
      <Point>
        <coordinates>-73.985,40.748,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Parking Lot</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.985,40.748,0
              -73.984,40.748,0
              -73.984,40.749,0
              -73.985,40.749,0
              -73.985,40.748,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

# Test Case 3: KML with exotic namespaces (simulating the problematic case)
problematic_kml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">
  <Document>
    <name>Problematic</name>
    <ns1:someElement>test</ns1:someElement>
    <Placemark>
      <name>Tank 1000 gal</name>
      <Point>
        <coordinates>-80.123,25.456,0</coordinates>
      </Point>
    </Placemark>
    <ns2:anotherElement>data</ns2:anotherElement>
    <Placemark>
      <name>Storage Area</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -80.123,25.456,0
              -80.122,25.456,0
              -80.122,25.457,0
              -80.123,25.457,0
              -80.123,25.456,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>"""

def test_kml_parser(kml_content, test_name):
    """Test the parser with different KML content"""
    print(f"\n{'='*50}")
    print(f"Testing: {test_name}")
    print('='*50)
    
    # Create temporary KMZ file
    with tempfile.NamedTemporaryFile(suffix='.kmz', delete=False) as tmp_kmz:
        kmz_path = tmp_kmz.name
        
        # Create KMZ with KML content
        with zipfile.ZipFile(kmz_path, 'w') as kmz:
            kmz.writestr('doc.kml', kml_content)
    
    try:
        # Initialize parser
        parser = KMZParserAgent(batch_size=10)
        
        # Create temp output dir
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Parse the KMZ
            result = parser.parse(kmz_path, tmp_dir)
            
            # Print results
            print(f"✅ Parsing successful!")
            print(f"   Polygons found: {len(result['polygons'])}")
            print(f"   Points found: {len(result['points'])}")
            print(f"   Errors: {len(result['errors'])}")
            
            if result['errors']:
                print(f"   ⚠️ Errors encountered:")
                for err in result['errors']:
                    print(f"      - {err}")
            
            # Show parsed features
            for polygon in result['polygons']:
                print(f"   📍 Polygon: {polygon['name']} ({len(polygon['coordinates'])} vertices)")
            
            for point in result['points']:
                print(f"   📌 Point: {point['name']} at ({point['latitude']:.4f}, {point['longitude']:.4f})")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        # Cleanup
        Path(kmz_path).unlink(missing_ok=True)

if __name__ == "__main__":
    print("Testing KMZ Parser with Various KML Configurations")
    print("="*50)
    
    tests = [
        (simple_kml, "Simple KML (no namespace issues)"),
        (qgis_style_kml, "QGIS-style KML (with gx namespace)"),
        (problematic_kml, "Problematic KML (with unbound ns1, ns2)")
    ]
    
    results = []
    for kml, name in tests:
        success = test_kml_parser(kml, name)
        results.append((name, success))
    
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ All tests passed!" if all_passed else "❌ Some tests failed"))