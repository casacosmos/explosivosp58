# Tank Compliance Assessment MCP Tools

## Overview
This MCP (Model Context Protocol) server provides a comprehensive set of tools for tank compliance assessment, including geospatial calculations, data parsing, and visualization generation.

## Key Functions

### 1. Data Parsing & Validation

#### `parse_tank_measurements`
- Parses tank measurement strings (e.g., "39"x46"x229"")
- Handles both cylindrical (2D) and rectangular (3D) tanks
- Calculates volume in gallons
- Fixes common formatting issues

#### `parse_multi_tank_capacities`
- Parses capacity strings with multiple tanks
- Identifies individual tank capacities
- Returns largest tank for compliance (not sum)
- Handles various formats (semicolon-separated, etc.)

#### `extract_asd_values`
- Extracts ASDPPU and ASDBPU values from text
- Handles complex ASD calculation strings
- Returns structured data for compliance assessment

### 2. Coordinate System Management

#### `parse_kmz_file`
- Extracts site locations from KMZ/KML files
- Parses polygon boundaries
- Handles Google Earth format complexities
- Returns structured site and polygon data

#### `convert_dms_to_decimal`
- Converts degrees/minutes/seconds to decimal degrees
- Handles all compass directions (N/S/E/W)
- Essential for manual coordinate entry

#### `match_sites_fuzzy`
- Matches site names between Excel and KMZ
- Uses fuzzy matching algorithms
- Handles name variations and typos
- Returns match scores and unmatched items

### 3. Geospatial Calculations

#### `calculate_distance_to_polygon`
- Calculates minimum distance from point to polygon boundary
- Uses UTM Zone 19N projection for Puerto Rico
- Returns distance in feet and meters
- Identifies closest boundary point
- Determines if point is inside/outside polygon

#### `batch_calculate_distances`
- Processes multiple sites efficiently
- Parallel distance calculations
- Handles missing coordinates gracefully

### 4. Compliance Assessment

#### `assess_compliance`
- Compares actual vs required distances
- Applies ASDPPU/ASDBPU rules based on dike presence
- Calculates safety margins
- Assigns risk levels for non-compliant sites

#### `process_excel_compliance`
- Processes entire Excel file
- Comprehensive compliance assessment
- Generates summary statistics
- Returns detailed results for each site

### 5. Visualization Generation

#### `create_kmz_file`
- Creates Google Earth visualization
- Color-codes sites by compliance status
- Includes polygon boundaries and buffers
- Customizable styles and labels

### 6. Data Integration

#### `update_excel_with_results`
- Updates original Excel with calculated data
- Preserves original format
- Adds compliance columns
- Maintains data integrity

## Installation

```bash
# Install required dependencies
pip install pandas numpy pyproj shapely

# Make server executable
chmod +x mcp_tank_compliance_server.py
```

## Usage Example

```python
# Initialize MCP client
mcp = MCPClient("tank-compliance")

# Parse tank measurements
result = await mcp.call('parse_tank_measurements', {
    'measurement_str': "39\"x46\"x229\""
})
# Returns: {'volume_gallons': 1778.0, 'shape': 'rectangular', ...}

# Calculate distance to boundary
distance = await mcp.call('calculate_distance_to_polygon', {
    'point_lat': 18.2302810,
    'point_lon': -65.9201257,
    'polygon_coords': boundary_coords
})
# Returns: {'distance_feet': 1855.72, 'is_inside': False, ...}

# Assess compliance
compliance = await mcp.call('assess_compliance', {
    'distance_feet': 1855.72,
    'asd_values': {'ASDPPU': 351.50, 'ASDBPU': 65.61},
    'has_dike': False
})
# Returns: {'status': 'COMPLIANT', 'margin': 1504.22, ...}
```

## Complete Pipeline Flow

1. **Input Processing**
   - Parse KMZ for locations and boundaries
   - Read Excel with tank data
   - Parse measurements and capacities

2. **Data Matching**
   - Match sites between Excel and KMZ
   - Handle name variations
   - Fill coordinate gaps

3. **Calculations**
   - Transform coordinates to proper projection
   - Calculate distances to boundaries
   - Determine inside/outside status

4. **Compliance Assessment**
   - Apply ASD requirements
   - Calculate margins
   - Assign risk levels

5. **Output Generation**
   - Create KMZ visualization
   - Update Excel with results
   - Generate compliance reports

## Special Features

### Coordinate System Handling
- Automatic projection to UTM Zone 19N for Puerto Rico
- Accurate distance calculations in feet
- Handles WGS84 input coordinates

### Multi-Tank Logic
- Identifies largest tank for compliance
- Doesn't sum capacities incorrectly
- Maintains individual tank records

### Error Handling
- Graceful handling of missing data
- Validation of coordinate bounds
- Clear error messages

### Visualization
- Color-coded compliance status
- Multiple polygon layers
- Customizable display names

## Configuration

The MCP server can be configured via `mcp_server_config.json`:

```json
{
  "name": "tank-compliance",
  "version": "1.0.0",
  "tools": [...],
  "dependencies": {
    "pandas": ">=2.0.0",
    "pyproj": ">=3.5.0",
    "shapely": ">=2.0.0"
  }
}
```

## Testing

Run the usage example to test all tools:

```bash
python mcp_usage_example.py
```

## Key Technical Solutions

1. **Projection Issue**: Uses UTM Zone 19N instead of incorrect projections
2. **Tank Capacity**: Uses largest individual tank, not sum
3. **Name Matching**: Fuzzy matching handles variations
4. **Distance Calculation**: Minimum distance to polygon boundary, not centroid
5. **Compliance Logic**: Proper ASDPPU/ASDBPU selection based on dike presence

## Output Files

- `tank_compliance_final.xlsx` - Updated Excel with all calculations
- `tank_compliance_output.kmz` - Google Earth visualization
- Preserves original data while adding analysis columns

## Support

For issues or questions about the MCP tools, refer to:
- Tool documentation in `mcp_server_config.json`
- Usage examples in `mcp_usage_example.py`
- Implementation details in `mcp_tank_compliance_server.py`