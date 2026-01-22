#!/usr/bin/env python3
"""
HUD ASD Calculator Browser Automation Tool
Automates the HUD calculator to get compliance distances and generate PDF reports
"""

import asyncio
import json
import base64
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass
from PIL import Image
import io

# Browser automation
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright.sync_api import sync_playwright

# PDF generation
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TankData:
    """Tank data for HUD calculation"""
    site_name: str
    tank_capacity: float
    tank_type: str = "AST"  # Above-ground Storage Tank
    contents: str = "Gasoline"
    has_dike: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class HUDResult:
    """HUD calculation result"""
    site_name: str
    tank_capacity: float
    asdppu: float
    asdbpu: float
    screenshot_path: Optional[str] = None
    calculation_date: str = ""
    error: Optional[str] = None


class HUDASDAutomation:
    """HUD ASD Calculator automation tool"""

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.results: List[HUDResult] = []
        self.screenshots_dir = Path("hud_screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)

        # HUD Calculator URL
        self.hud_url = "https://www.hud.gov/program_offices/housing/rmra/sfh/hse/ASD_Calculator"

    async def initialize_browser(self, headless: bool = False):
        """Initialize Playwright browser"""
        try:
            playwright = await async_playwright().start()

            # Launch browser with specific args for stability
            self.browser = await playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-gpu'
                ]
            )

            # Create context with viewport and user agent
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 1024},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            self.page = await self.context.new_page()

            logger.info("Browser initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    async def navigate_to_calculator(self) -> bool:
        """Navigate to HUD ASD Calculator"""
        try:
            await self.page.goto(self.hud_url, wait_until='networkidle', timeout=30000)

            # Wait for calculator to load
            await self.page.wait_for_selector('input[type="text"]', timeout=10000)

            logger.info("Successfully navigated to HUD calculator")
            return True

        except Exception as e:
            logger.error(f"Failed to navigate to calculator: {e}")
            return False

    async def fill_tank_data(self, tank: TankData) -> bool:
        """Fill in tank data on the HUD calculator form"""
        try:
            # Clear any existing values first
            await self.page.evaluate('''() => {
                document.querySelectorAll('input[type="text"]').forEach(input => input.value = '');
                document.querySelectorAll('input[type="number"]').forEach(input => input.value = '');
            }''')

            # Tank capacity input (usually first input field)
            capacity_input = await self.page.query_selector('input[name*="capacity"], input[id*="capacity"], input[placeholder*="gallons"]')
            if not capacity_input:
                # Try generic approach
                capacity_input = await self.page.query_selector('input[type="text"]:first-of-type, input[type="number"]:first-of-type')

            if capacity_input:
                await capacity_input.click()
                await capacity_input.fill(str(int(tank.tank_capacity)))
                logger.info(f"Filled capacity: {tank.tank_capacity} gallons")

            # Select tank type (AST/UST)
            tank_type_select = await self.page.query_selector('select[name*="tank"], select[id*="tank"]')
            if tank_type_select:
                await tank_type_select.select_option(value=tank.tank_type)
                logger.info(f"Selected tank type: {tank.tank_type}")

            # Select contents (Gasoline/Diesel/etc)
            contents_select = await self.page.query_selector('select[name*="content"], select[id*="content"], select[name*="fuel"]')
            if contents_select:
                await contents_select.select_option(label=tank.contents)
                logger.info(f"Selected contents: {tank.contents}")

            # Check/uncheck dike checkbox if present
            dike_checkbox = await self.page.query_selector('input[type="checkbox"][name*="dike"], input[type="checkbox"][id*="dike"]')
            if dike_checkbox:
                is_checked = await dike_checkbox.is_checked()
                if is_checked != tank.has_dike:
                    await dike_checkbox.click()
                logger.info(f"Dike setting: {tank.has_dike}")

            return True

        except Exception as e:
            logger.error(f"Failed to fill tank data: {e}")
            return False

    async def calculate_asd(self) -> Tuple[Optional[float], Optional[float]]:
        """Click calculate and extract ASD values"""
        try:
            # Find and click calculate button
            calc_button = await self.page.query_selector('button[type="submit"], input[type="submit"], button:has-text("Calculate")')
            if not calc_button:
                calc_button = await self.page.query_selector('button, input[type="button"]')

            if calc_button:
                await calc_button.click()
                logger.info("Clicked calculate button")

                # Wait for results
                await self.page.wait_for_timeout(2000)

                # Extract ASDPPU value
                asdppu_text = await self.page.text_content('*:has-text("ASDPPU") + *, *:has-text("without dike") + *')
                asdppu = self._extract_number(asdppu_text) if asdppu_text else None

                # Extract ASDBPU value
                asdbpu_text = await self.page.text_content('*:has-text("ASDBPU") + *, *:has-text("with dike") + *')
                asdbpu = self._extract_number(asdbpu_text) if asdbpu_text else None

                # Alternative extraction method
                if not asdppu or not asdbpu:
                    result_text = await self.page.text_content('body')
                    import re

                    asdppu_match = re.search(r'ASDPPU[:\s]+([0-9.,]+)\s*(?:feet|ft)?', result_text, re.IGNORECASE)
                    if asdppu_match:
                        asdppu = self._extract_number(asdppu_match.group(1))

                    asdbpu_match = re.search(r'ASDBPU[:\s]+([0-9.,]+)\s*(?:feet|ft)?', result_text, re.IGNORECASE)
                    if asdbpu_match:
                        asdbpu = self._extract_number(asdbpu_match.group(1))

                logger.info(f"Extracted values - ASDPPU: {asdppu}, ASDBPU: {asdbpu}")
                return asdppu, asdbpu

        except Exception as e:
            logger.error(f"Failed to calculate ASD: {e}")
            return None, None

    def _extract_number(self, text: str) -> Optional[float]:
        """Extract number from text string"""
        if not text:
            return None

        import re
        # Remove commas and extract number
        match = re.search(r'([0-9,]+\.?[0-9]*)', text)
        if match:
            number_str = match.group(1).replace(',', '')
            try:
                return float(number_str)
            except ValueError:
                return None
        return None

    async def capture_screenshot(self, tank_name: str) -> Optional[str]:
        """Capture screenshot of the calculation results"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in tank_name)
            filename = f"hud_{safe_name}_{timestamp}.png"
            filepath = self.screenshots_dir / filename

            # Capture full page screenshot
            await self.page.screenshot(path=str(filepath), full_page=True)

            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    async def process_tank(self, tank: TankData) -> HUDResult:
        """Process a single tank through HUD calculator"""
        logger.info(f"Processing tank: {tank.site_name} ({tank.tank_capacity} gal)")

        result = HUDResult(
            site_name=tank.site_name,
            tank_capacity=tank.tank_capacity,
            asdppu=0,
            asdbpu=0,
            calculation_date=datetime.now().isoformat()
        )

        try:
            # Navigate to calculator
            if not await self.navigate_to_calculator():
                result.error = "Failed to navigate to calculator"
                return result

            # Fill tank data
            if not await self.fill_tank_data(tank):
                result.error = "Failed to fill tank data"
                return result

            # Calculate ASD
            asdppu, asdbpu = await self.calculate_asd()
            if asdppu is None or asdbpu is None:
                result.error = "Failed to extract ASD values"
                return result

            result.asdppu = asdppu
            result.asdbpu = asdbpu

            # Capture screenshot
            screenshot_path = await self.capture_screenshot(tank.site_name)
            result.screenshot_path = screenshot_path

            logger.info(f"Successfully processed {tank.site_name}: ASDPPU={asdppu}, ASDBPU={asdbpu}")

        except Exception as e:
            logger.error(f"Error processing tank {tank.site_name}: {e}")
            result.error = str(e)

        return result

    async def process_tanks_batch(self, tanks: List[TankData]) -> List[HUDResult]:
        """Process multiple tanks in batch"""
        results = []

        # Initialize browser once
        if not await self.initialize_browser(headless=True):
            logger.error("Failed to initialize browser for batch processing")
            return results

        try:
            for i, tank in enumerate(tanks, 1):
                logger.info(f"Processing tank {i}/{len(tanks)}: {tank.site_name}")

                result = await self.process_tank(tank)
                results.append(result)
                self.results.append(result)

                # Small delay between calculations
                await asyncio.sleep(2)

        finally:
            await self.cleanup()

        return results

    async def cleanup(self):
        """Clean up browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            logger.info("Browser cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def generate_pdf_report(self, results: List[HUDResult], output_path: str = "hud_compliance_report.pdf") -> str:
        """Generate PDF report with screenshots and results"""

        doc = SimpleDocTemplate(output_path, pagesize=letter)
        story = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2E4C6D'),
            spaceAfter=30,
            alignment=1  # Center
        )

        story.append(Paragraph("HUD ASD Compliance Report", title_style))
        story.append(Spacer(1, 20))

        # Date
        date_style = ParagraphStyle(
            'DateStyle',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#666666'),
            alignment=1
        )
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}", date_style))
        story.append(Spacer(1, 30))

        # Summary table
        summary_data = [['Site Name', 'Tank Capacity (gal)', 'ASDPPU (ft)', 'ASDBPU (ft)', 'Status']]

        for result in results:
            status = "✓" if result.error is None else "✗"
            summary_data.append([
                result.site_name[:30],
                f"{result.tank_capacity:,.0f}",
                f"{result.asdppu:,.2f}" if result.asdppu else "N/A",
                f"{result.asdbpu:,.2f}" if result.asdbpu else "N/A",
                status
            ])

        summary_table = Table(summary_data, colWidths=[200, 100, 80, 80, 50])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4C6D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        story.append(summary_table)
        story.append(PageBreak())

        # Individual tank details with screenshots
        for result in results:
            # Tank header
            tank_header = ParagraphStyle(
                'TankHeader',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#2E4C6D'),
                spaceAfter=10
            )

            story.append(Paragraph(f"Tank: {result.site_name}", tank_header))

            # Tank details
            details_data = [
                ['Property', 'Value'],
                ['Tank Capacity', f"{result.tank_capacity:,.0f} gallons"],
                ['ASDPPU', f"{result.asdppu:,.2f} feet" if result.asdppu else "N/A"],
                ['ASDBPU', f"{result.asdbpu:,.2f} feet" if result.asdbpu else "N/A"],
                ['Calculation Date', result.calculation_date[:19] if result.calculation_date else "N/A"],
                ['Status', "Success" if result.error is None else f"Error: {result.error}"]
            ]

            details_table = Table(details_data, colWidths=[150, 300])
            details_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))

            story.append(details_table)
            story.append(Spacer(1, 20))

            # Add screenshot if available
            if result.screenshot_path and Path(result.screenshot_path).exists():
                try:
                    img = RLImage(result.screenshot_path, width=500, height=400)
                    story.append(img)
                except Exception as e:
                    logger.error(f"Failed to add screenshot to PDF: {e}")
                    story.append(Paragraph(f"Screenshot unavailable: {e}", styles['Normal']))

            story.append(PageBreak())

        # Build PDF
        doc.build(story)
        logger.info(f"PDF report generated: {output_path}")
        return output_path

    async def export_results_json(self, output_path: str = "hud_results.json") -> str:
        """Export results to JSON file"""
        results_data = []

        for result in self.results:
            results_data.append({
                'site_name': result.site_name,
                'tank_capacity': result.tank_capacity,
                'asdppu': result.asdppu,
                'asdbpu': result.asdbpu,
                'screenshot_path': result.screenshot_path,
                'calculation_date': result.calculation_date,
                'error': result.error
            })

        with open(output_path, 'w') as f:
            json.dump(results_data, f, indent=2)

        logger.info(f"Results exported to JSON: {output_path}")
        return output_path


# ============ MCP Tool Interface ============

async def process_hud_calculations(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool for processing HUD ASD calculations

    Args:
        tanks: List of tank data dictionaries
        generate_pdf: Whether to generate PDF report
        capture_screenshots: Whether to capture screenshots
        headless: Whether to run browser in headless mode

    Returns:
        Dictionary with results and file paths
    """
    automation = HUDASDAutomation()

    # Parse tank data
    tanks = []
    for tank_data in params.get('tanks', []):
        tank = TankData(
            site_name=tank_data['site_name'],
            tank_capacity=float(tank_data['tank_capacity']),
            tank_type=tank_data.get('tank_type', 'AST'),
            contents=tank_data.get('contents', 'Gasoline'),
            has_dike=tank_data.get('has_dike', False),
            latitude=tank_data.get('latitude'),
            longitude=tank_data.get('longitude')
        )
        tanks.append(tank)

    # Process tanks
    results = await automation.process_tanks_batch(tanks)

    # Generate outputs
    output_files = []

    if params.get('generate_pdf', True):
        pdf_path = automation.generate_pdf_report(results)
        output_files.append(pdf_path)

    # Export JSON results
    json_path = await automation.export_results_json()
    output_files.append(json_path)

    # Format results for return
    formatted_results = []
    for result in results:
        formatted_results.append({
            'site_name': result.site_name,
            'tank_capacity': result.tank_capacity,
            'asdppu': result.asdppu,
            'asdbpu': result.asdbpu,
            'asd_string': f"ASDPPU: {result.asdppu:.2f} ft, ASDBPU: {result.asdbpu:.2f} ft",
            'screenshot_path': result.screenshot_path,
            'error': result.error
        })

    return {
        'success': True,
        'results': formatted_results,
        'output_files': output_files,
        'summary': {
            'total_processed': len(results),
            'successful': len([r for r in results if r.error is None]),
            'failed': len([r for r in results if r.error is not None])
        }
    }


# Standalone execution
async def main():
    """Test the HUD automation tool"""

    # Example tanks
    test_tanks = [
        TankData("CDT Juncos", 1778),
        TankData("Juegos Caray", 397),
        TankData("Coliseo Rafael G Amalbert", 964),
    ]

    automation = HUDASDAutomation()
    results = await automation.process_tanks_batch(test_tanks)

    # Generate PDF report
    if results:
        automation.generate_pdf_report(results)
        await automation.export_results_json()

    print(f"Processed {len(results)} tanks")
    for result in results:
        if result.error is None:
            print(f"  {result.site_name}: ASDPPU={result.asdppu}, ASDBPU={result.asdbpu}")
        else:
            print(f"  {result.site_name}: ERROR - {result.error}")


if __name__ == "__main__":
    asyncio.run(main())