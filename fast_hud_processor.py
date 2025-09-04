#!/usr/bin/env python3
"""
Fast HUD ASD Calculator Processor
Optimized version that reuses browser session and minimizes page loads
"""

import asyncio
import json
import argparse
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Page
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class FastHUDProcessor:
    """Optimized HUD processor that minimizes page loads"""
    
    def __init__(self):
        self.url = "https://www.hudexchange.info/programs/environmental-review/asd-calculator/"
        self.page: Optional[Page] = None
        self.results = []
        
    async def setup(self):
        """Setup browser and navigate once"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False)
        self.page = await self.browser.new_page()
        
        # Navigate once at the beginning
        await self.page.goto(self.url)
        await self.page.wait_for_load_state('networkidle')
        logger.info("Browser ready, page loaded once")
        
    async def cleanup(self):
        """Cleanup resources"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def reset_form(self):
        """Reset form to initial state using JavaScript"""
        reset_js = """
        () => {
            // Reset all checkboxes
            document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                cb.checked = false;
            });
            
            // Clear all text inputs
            document.querySelectorAll('input[type="text"]').forEach(input => {
                input.value = '';
            });
            
            // Clear result fields
            const resultFields = ['asdppu', 'asdbpu', 'asdpnpd', 'asdbnpd', 'asdbop'];
            resultFields.forEach(field => {
                const input = document.querySelector(`input[name="${field}"]`);
                if (input) input.value = '';
            });
            
            return "Form reset";
        }
        """
        await self.page.evaluate(reset_js)
        
    async def process_tank_fast(self, tank: Dict) -> Dict:
        """Process a single tank with minimal overhead"""
        
        logger.info(f"Processing Tank {tank['id']}: {tank['name']} ({tank['volume']} gal)")
        
        # Reset form for new tank
        await self.reset_form()
        await asyncio.sleep(0.5)
        
        # Determine tank characteristics
        is_pressurized = tank.get('type') == 'pressurized_gas'
        is_cryogenic = is_pressurized  # For pressurized gas, set cryogenic to True
        has_dike = tank.get('has_dike', False)
        
        # Fill form using optimized JavaScript with visual confirmation
        fill_js = """
        async (tank) => {
            // Helper to click checkbox and ensure it's visually checked
            const clickCheckbox = async (partialId, value) => {
                const selector = `input[type="checkbox"][id*="${partialId}"][value="${value}"]`;
                const checkbox = document.querySelector(selector);
                if (checkbox) {
                    // First set the checked property
                    checkbox.checked = true;
                    // Then trigger click event for any handlers
                    checkbox.click();
                    // Force visual update
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                    await new Promise(r => setTimeout(r, 150));
                }
            };
            
            // Helper to ensure checkbox is visually set
            const ensureChecked = (partialId, value, shouldBeChecked) => {
                const selector = `input[type="checkbox"][id*="${partialId}"][value="${value}"]`;
                const checkbox = document.querySelector(selector);
                if (checkbox) {
                    checkbox.checked = shouldBeChecked;
                }
            };
            
            // Step 1: Above ground - Yes
            await clickCheckbox('chkAboveGround', 'Yes');
            ensureChecked('chkAboveGround', 'Yes', true);
            
            // Step 2: Under pressure
            const pressureValue = tank.is_pressurized ? 'Yes' : 'No';
            await clickCheckbox('chkPressurized', pressureValue);
            ensureChecked('chkPressurized', pressureValue, true);
            
            // Step 3: Cryogenic (if pressurized)
            if (tank.is_pressurized) {
                const cryoValue = tank.is_cryogenic ? 'Yes' : 'No';
                await clickCheckbox('chkCryogen', cryoValue);
                ensureChecked('chkCryogen', cryoValue, true);
            }
            
            // Step 4: Diked
            const dikeValue = tank.has_dike ? 'Yes' : 'No';
            await clickCheckbox('chkDiked', dikeValue);
            ensureChecked('chkDiked', dikeValue, true);
            
            // Step 5: Volume
            await new Promise(r => setTimeout(r, 200));
            const volumeInput = document.querySelector('input[name="volume"]');
            if (volumeInput) {
                volumeInput.disabled = false;
                volumeInput.value = tank.volume;
                volumeInput.dispatchEvent(new Event('input', { bubbles: true }));
            }
            
            // Step 6: Dike dimensions (if applicable)
            if (tank.has_dike && tank.dike_length && tank.dike_width) {
                const lengthInput = document.querySelector('input[name="dikedLength"]');
                const widthInput = document.querySelector('input[name="dikedWidth"]');
                
                if (lengthInput) {
                    lengthInput.disabled = false;
                    lengthInput.value = tank.dike_length;
                }
                if (widthInput) {
                    widthInput.disabled = false;
                    widthInput.value = tank.dike_width;
                }
            }
            
            // Final wait to ensure visual state is updated
            await new Promise(r => setTimeout(r, 300));
            
            return "Form filled";
        }
        """
        
        # Prepare tank data for JavaScript
        tank_data = {
            'volume': tank['volume'],
            'is_pressurized': is_pressurized,
            'is_cryogenic': is_cryogenic,
            'has_dike': has_dike,
            'dike_length': tank.get('dike_dims', [None, None])[0] if has_dike else None,
            'dike_width': tank.get('dike_dims', [None, None])[1] if has_dike else None
        }
        
        await self.page.evaluate(fill_js, tank_data)
        await asyncio.sleep(0.5)
        
        # Double-check checkboxes are visually set before screenshot
        await self.page.evaluate("""
            () => {
                // Force all checked checkboxes to show as checked
                document.querySelectorAll('input[type="checkbox"]:checked').forEach(cb => {
                    cb.checked = true;
                    cb.setAttribute('checked', 'checked');
                });
            }
        """)
        
        # Click calculate button - use a more specific selector
        try:
            # Try multiple selectors
            await self.page.click('input[type="button"][value="Calculate Acceptable Separation Distance"]', timeout=5000)
        except:
            try:
                await self.page.click('button:text("Calculate Acceptable Separation Distance")', timeout=5000)
            except:
                # Fallback to JavaScript click
                await self.page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button, input[type="button"]');
                        for (const btn of buttons) {
                            if (btn.textContent.includes('Calculate') || btn.value.includes('Calculate')) {
                                btn.click();
                                break;
                            }
                        }
                    }
                """)
        await asyncio.sleep(1)
        
        # Extract results - wait a bit for calculation to complete
        await asyncio.sleep(0.5)
        results_js = """
        () => {
            // Try multiple ways to get the values
            const getVal = (possibleNames) => {
                for (const name of possibleNames) {
                    // Try by name attribute
                    let input = document.querySelector(`input[name="${name}"]`);
                    if (input && input.value) return input.value;
                    
                    // Try by id
                    input = document.querySelector(`input[id*="${name}"]`);
                    if (input && input.value) return input.value;
                    
                    // Try by nearby label text
                    const labels = document.querySelectorAll('td');
                    for (const label of labels) {
                        if (label.textContent.includes(name.toUpperCase()) || 
                            label.textContent.includes('ASDPPU') || 
                            label.textContent.includes('ASDBPU')) {
                            const nextCell = label.nextElementSibling;
                            if (nextCell) {
                                const input = nextCell.querySelector('input');
                                if (input && input.value) return input.value;
                            }
                        }
                    }
                }
                return null;
            };
            
            // Get all input values for debugging
            const allInputs = {};
            document.querySelectorAll('input[type="text"]').forEach(input => {
                if (input.value && input.name) {
                    allInputs[input.name] = input.value;
                }
            });
            
            // The actual field names from the debug output
            return {
                asdppu: allInputs['ppuResult'] || getVal(['asdppu', 'ASDPPU', 'txtASDPPU']),
                asdbpu: allInputs['bpuResult'] || getVal(['asdbpu', 'ASDBPU', 'txtASDBPU']),
                asdpnpd: allInputs['pnpdResult'] || getVal(['asdpnpd', 'ASDPNPD', 'txtASDPNPD']),
                asdbnpd: allInputs['bnpdResult'] || getVal(['asdbnpd', 'ASDBNPD', 'txtASDBNPD']),
                volume: allInputs['volume'],
                debug: allInputs
            };
        }
        """
        
        results = await self.page.evaluate(results_js)
        
        # Take screenshot if needed
        screenshot_path = None
        if tank.get('screenshot', True):
            import os
            os.makedirs('.playwright-mcp', exist_ok=True)
            
            # First, try to force checkboxes to show as visually checked
            await self.page.evaluate("""
                () => {
                    // Force re-render of checkboxes by toggling them
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    checkboxes.forEach(cb => {
                        if (cb.checked) {
                            // Store the state
                            const wasChecked = true;
                            // Toggle off and on to force visual update
                            cb.checked = false;
                            cb.offsetHeight; // Force reflow
                            cb.checked = true;
                            cb.setAttribute('checked', 'checked');
                            // Trigger change event
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    });
                    
                    // Also ensure the volume field is visible
                    const volumeInput = document.querySelector('input[name="volume"]');
                    if (volumeInput && volumeInput.value) {
                        volumeInput.style.backgroundColor = '#ffffcc'; // Light yellow to show it's filled
                        setTimeout(() => {
                            volumeInput.style.backgroundColor = ''; // Reset after screenshot
                        }, 2000);
                    }
                }
            """)
            
            # Small wait for visual update
            await asyncio.sleep(0.3)
            
            filename = f".playwright-mcp/tank-{tank['id']:02d}-{tank['name'].replace(' ', '-').replace('/', '-')}-{tank['volume']}gal.png"
            await self.page.screenshot(path=filename, full_page=True)
            screenshot_path = filename
            logger.info(f"  → Screenshot saved: {filename}")
            
        tank_result = {
            'tank_id': tank['id'],
            'name': tank['name'],
            'volume': tank['volume'],
            'type': tank.get('type', 'diesel'),
            'has_dike': has_dike,
            'results': results,
            'screenshot': screenshot_path
        }
        
        self.results.append(tank_result)
        
        # Log results
        if results.get('debug'):
            logger.debug(f"  → Debug values found: {results['debug']}")
        logger.info(f"  → ASDPPU: {results.get('asdppu', 'N/A')} ft, ASDBPU: {results.get('asdbpu', 'N/A')} ft")
        
        return tank_result
        
    async def process_batch(self, tanks: List[Dict]) -> List[Dict]:
        """Process multiple tanks efficiently"""
        
        await self.setup()
        
        try:
            for tank in tanks:
                await self.process_tank_fast(tank)
                
        finally:
            await self.cleanup()
            
        return self.results


async def main():
    """CLI entrypoint for fast HUD processing"""
    parser = argparse.ArgumentParser(description="Fast HUD ASD processor")
    parser.add_argument("--config", "-c", default="tank_configurations.json", help="Path to tank configuration JSON")
    args = parser.parse_args()

    # Load tanks from configuration
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    tanks = config['tanks']
    
    # Process with fast processor
    processor = FastHUDProcessor()
    results = await processor.process_batch(tanks)
    
    # Save results
    with open('fast_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print("FAST PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Processed {len(results)} tanks")
    print("\nResults:")
    for r in results:
        print(f"  {r['name']}: ASDPPU={r['results']['asdppu']}ft, ASDBPU={r['results']['asdbpu']}ft")
    
    # Generate PDF from screenshots
    print(f"\n{'='*60}")
    print("GENERATING PDF")
    print(f"{'='*60}")
    
    try:
        from generate_pdf import combine_screenshots_to_pdf
        pdf_success = combine_screenshots_to_pdf(
            output_pdf="HUD_ASD_Results.pdf",
            screenshot_dir=".playwright-mcp",
            include_metadata=True
        )
        if pdf_success:
            print("✅ PDF generated successfully: HUD_ASD_Results.pdf")
    except ImportError:
        print("⚠️  PDF generation module not found. Run separately with:")
        print("    python generate_pdf.py")
    except Exception as e:
        print(f"⚠️  PDF generation failed: {e}")
        print("    You can generate PDF manually with: python generate_pdf.py")


if __name__ == "__main__":
    asyncio.run(main())
