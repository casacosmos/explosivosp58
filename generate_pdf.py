#!/usr/bin/env python3
"""
Generate PDF from HUD ASD Calculator screenshots
Combines all screenshots from .playwright-mcp/ into a single PDF
"""

from PIL import Image
import os
import glob
import json
from datetime import datetime
from pathlib import Path
import argparse

def get_screenshots(directory=".playwright-mcp", pattern="*.png"):
    """Get all screenshot files from directory"""
    screenshot_dir = Path(directory)
    if not screenshot_dir.exists():
        print(f"❌ Screenshot directory not found: {directory}")
        return []
    
    # Get all PNG files and sort them
    screenshots = sorted(glob.glob(str(screenshot_dir / pattern)))
    
    # Try to sort by tank ID if present in filename
    def extract_tank_number(filename):
        import re
        # Look for patterns like tank-01, tank-1, etc.
        match = re.search(r'tank-?(\d+)', Path(filename).name, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return 999  # Put non-numbered files at end
    
    screenshots.sort(key=extract_tank_number)
    
    return screenshots

def combine_screenshots_to_pdf(
    screenshots=None, 
    output_pdf="HUD_ASD_Results.pdf",
    screenshot_dir=".playwright-mcp",
    include_metadata=True
):
    """
    Combine multiple screenshots into a single PDF
    
    Args:
        screenshots: List of screenshot paths (if None, finds all in directory)
        output_pdf: Output PDF filename
        screenshot_dir: Directory containing screenshots
        include_metadata: Whether to read tank data from JSON
    """
    
    # Get screenshots if not provided
    if screenshots is None:
        screenshots = get_screenshots(screenshot_dir)
    
    if not screenshots:
        print("❌ No screenshots found to convert!")
        return False
    
    print(f"\n📸 Found {len(screenshots)} screenshots to combine")
    
    # Convert screenshots to PIL Image objects
    images = []
    for i, screenshot_path in enumerate(screenshots, 1):
        try:
            img = Image.open(screenshot_path)
            # Convert to RGB if necessary (PNG might be RGBA)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
            print(f"  ✓ Loaded {i}/{len(screenshots)}: {Path(screenshot_path).name}")
        except Exception as e:
            print(f"  ❌ Error loading {screenshot_path}: {e}")
    
    if not images:
        print("❌ No images could be loaded!")
        return False
    
    # Save all images as a single PDF
    print(f"\n📄 Creating PDF: {output_pdf}")
    
    try:
        # First image is saved with all others appended
        images[0].save(
            output_pdf,
            "PDF",
            resolution=100.0,
            save_all=True,
            append_images=images[1:]
        )
        print(f"✅ PDF created successfully: {output_pdf}")
        print(f"   Pages: {len(images)}")
        print(f"   Size: {os.path.getsize(output_pdf) / 1024:.1f} KB")
        
        # Add metadata if available
        if include_metadata and Path("fast_results.json").exists():
            try:
                with open("fast_results.json", "r") as f:
                    results = json.load(f)
                
                print(f"\n📊 Tank Summary:")
                for result in results[:5]:  # Show first 5
                    name = result.get('name', 'Unknown')
                    volume = result.get('volume', 0)
                    asdppu = result.get('results', {}).get('asdppu', 'N/A')
                    asdbpu = result.get('results', {}).get('asdbpu', 'N/A')
                    print(f"   • {name} ({volume} gal): ASDPPU={asdppu}ft, ASDBPU={asdbpu}ft")
                
                if len(results) > 5:
                    print(f"   ... and {len(results) - 5} more tanks")
                    
            except Exception as e:
                print(f"   (Could not load metadata: {e})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating PDF: {e}")
        return False

def create_summary_page(results_json="fast_results.json"):
    """Create a summary page image from results JSON"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    
    if not Path(results_json).exists():
        return None
    
    with open(results_json, "r") as f:
        results = json.load(f)
    
    # Create summary image
    width, height = 800, 1100
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a better font, fall back to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        header_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except:
        title_font = ImageFont.load_default()
        header_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    y_position = 50
    
    # Title
    draw.text((width/2 - 200, y_position), "HUD ASD Calculator Results", font=title_font, fill='black')
    y_position += 40
    
    # Date
    draw.text((width/2 - 100, y_position), datetime.now().strftime("%B %d, %Y"), font=body_font, fill='gray')
    y_position += 40
    
    # Summary stats
    total_tanks = len(results)
    tank_types = {}
    dike_count = 0
    
    for r in results:
        tank_type = r.get('type', 'unknown')
        tank_types[tank_type] = tank_types.get(tank_type, 0) + 1
        if r.get('has_dike'):
            dike_count += 1
    
    draw.text((50, y_position), f"Total Tanks: {total_tanks}", font=header_font, fill='black')
    y_position += 30
    
    for tank_type, count in tank_types.items():
        draw.text((70, y_position), f"• {tank_type}: {count}", font=body_font, fill='black')
        y_position += 20
    
    draw.text((50, y_position), f"Tanks with Dikes: {dike_count}", font=header_font, fill='black')
    y_position += 40
    
    # Results table header
    draw.text((50, y_position), "Tank Name", font=header_font, fill='black')
    draw.text((350, y_position), "Volume", font=header_font, fill='black')
    draw.text((450, y_position), "ASDPPU", font=header_font, fill='black')
    draw.text((550, y_position), "ASDBPU", font=header_font, fill='black')
    draw.text((650, y_position), "Dike", font=header_font, fill='black')
    y_position += 25
    
    # Draw line
    draw.line((50, y_position, width-50, y_position), fill='gray', width=1)
    y_position += 10
    
    # Results rows (show up to 30)
    for i, result in enumerate(results[:30]):
        if y_position > height - 50:
            draw.text((50, height - 30), f"... and {len(results) - i} more tanks", font=body_font, fill='gray')
            break
        
        name = result.get('name', 'Unknown')[:30]
        volume = f"{result.get('volume', 0):.0f} gal"
        asdppu = result.get('results', {}).get('asdppu', 'N/A')
        asdbpu = result.get('results', {}).get('asdbpu', 'N/A')
        has_dike = "Yes" if result.get('has_dike') else "No"
        
        draw.text((50, y_position), name, font=body_font, fill='black')
        draw.text((350, y_position), volume, font=body_font, fill='black')
        draw.text((450, y_position), f"{asdppu} ft", font=body_font, fill='black')
        draw.text((550, y_position), f"{asdbpu} ft", font=body_font, fill='black')
        draw.text((650, y_position), has_dike, font=body_font, fill='black')
        
        y_position += 20
    
    return img

def main():
    parser = argparse.ArgumentParser(
        description='Generate PDF from HUD ASD Calculator screenshots'
    )
    parser.add_argument(
        '-d', '--directory',
        default='.playwright-mcp',
        help='Screenshot directory (default: .playwright-mcp)'
    )
    parser.add_argument(
        '-o', '--output',
        default='HUD_ASD_Results.pdf',
        help='Output PDF filename (default: HUD_ASD_Results.pdf)'
    )
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Include summary page at beginning'
    )
    parser.add_argument(
        '--pattern',
        default='*.png',
        help='Screenshot filename pattern (default: *.png)'
    )
    
    args = parser.parse_args()
    
    print("╔════════════════════════════════════════╗")
    print("║     HUD ASD PDF Generator              ║")
    print("╚════════════════════════════════════════╝")
    
    # Get screenshots
    screenshots = get_screenshots(args.directory, args.pattern)
    
    # Add summary page if requested
    if args.summary:
        summary_img = create_summary_page()
        if summary_img:
            # Save summary as temporary image
            summary_path = Path(args.directory) / "_00_summary.png"
            summary_img.save(summary_path)
            screenshots.insert(0, str(summary_path))
            print("✓ Added summary page")
    
    # Generate PDF
    success = combine_screenshots_to_pdf(
        screenshots=screenshots,
        output_pdf=args.output,
        include_metadata=True
    )
    
    # Clean up temporary summary if created
    if args.summary:
        summary_path = Path(args.directory) / "_00_summary.png"
        if summary_path.exists():
            summary_path.unlink()
    
    if success:
        print(f"\n✨ Done! PDF saved as: {args.output}")
    else:
        print("\n❌ PDF generation failed")
        exit(1)

if __name__ == "__main__":
    main()