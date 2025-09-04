#!/usr/bin/env python3
"""
Main Pipeline Orchestrator for Tank Processing System
Consolidates all pipeline steps into a single, configurable execution flow.
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import traceback


class PipelineStep(Enum):
    """Pipeline step identifiers"""
    KMZ_PARSE = "kmz_parse"
    EXCEL_TO_JSON = "excel_to_json"
    VALIDATE_JSON = "validate_json"
    HUD_PROCESS = "hud_process"
    GENERATE_PDF = "generate_pdf"
    UPDATE_EXCEL = "update_excel"
    CALCULATE_DISTANCES = "calculate_distances"
    CHECK_COMPLIANCE = "check_compliance"


@dataclass
class StepResult:
    """Result of a pipeline step execution"""
    step: PipelineStep
    success: bool
    output_file: Optional[Path] = None
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0


@dataclass
class PipelineConfig:
    """Pipeline configuration settings"""
    input_file: Path
    output_dir: Path = Path("outputs")
    use_improved_parser: bool = True
    skip_validation: bool = False
    debug: bool = False
    max_retries: int = 2
    session_id: Optional[str] = None
    preserve_columns: bool = True
    generate_normalized_copy: bool = False
    

class PipelineOrchestrator:
    """Main pipeline orchestrator for tank processing"""
    
    # Step dependencies mapping
    STEP_DEPENDENCIES = {
        PipelineStep.EXCEL_TO_JSON: [],
        PipelineStep.VALIDATE_JSON: [PipelineStep.EXCEL_TO_JSON],
        PipelineStep.HUD_PROCESS: [PipelineStep.EXCEL_TO_JSON],
        PipelineStep.GENERATE_PDF: [PipelineStep.HUD_PROCESS],
        PipelineStep.UPDATE_EXCEL: [PipelineStep.HUD_PROCESS],
        PipelineStep.CALCULATE_DISTANCES: [PipelineStep.EXCEL_TO_JSON],
        PipelineStep.CHECK_COMPLIANCE: [PipelineStep.UPDATE_EXCEL],
    }
    
    def __init__(self, config: PipelineConfig):
        """Initialize pipeline with configuration"""
        self.config = config
        self.results: Dict[PipelineStep, StepResult] = {}
        self.artifacts: Dict[str, Path] = {}
        
        # Create output directory
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Set session ID if not provided
        if not self.config.session_id:
            self.config.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Configure logging
        self.log_file = self.config.output_dir / f"pipeline_{self.config.session_id}.log"
        
    def log(self, message: str, level: str = "INFO"):
        """Log message to console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color codes for console output
        colors = {
            "INFO": "\033[0;37m",    # White
            "SUCCESS": "\033[0;32m",  # Green
            "WARNING": "\033[1;33m",  # Yellow
            "ERROR": "\033[0;31m",    # Red
            "DEBUG": "\033[0;36m",    # Cyan
        }
        reset = "\033[0m"
        
        # Console output with color
        if level != "DEBUG" or self.config.debug:
            print(f"{colors.get(level, '')}{message}{reset}")
        
        # File output
        with open(self.log_file, 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    
    def run_command(self, cmd: List[str], cwd: Path = Path(".")) -> Tuple[int, str, str]:
        """Execute a command and return result"""
        self.log(f"Executing: {' '.join(cmd)}", "DEBUG")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)
    
    def check_environment(self) -> bool:
        """Check required environment variables and dependencies"""
        self.log("Checking environment...", "INFO")
        
        # Check OpenAI API key
        if not os.getenv("OPENAI_API_KEY"):
            self.log("OPENAI_API_KEY environment variable not set", "ERROR")
            return False
        
        # Check required Python modules
        required_modules = [
            ("pandas", "pandas"),
            ("langchain", "langchain"),
            ("langchain_openai", "langchain-openai"),
            ("langgraph", "langgraph"),
            ("pydantic", "pydantic"),
        ]
        
        missing_modules = []
        for module, package in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(package)
        
        if missing_modules:
            self.log(f"Missing Python packages: {', '.join(missing_modules)}", "ERROR")
            self.log(f"Install with: pip install {' '.join(missing_modules)}", "ERROR")
            return False
        
        # Check for critical scripts
        if self.config.use_improved_parser:
            if not Path("volume_calculator.py").exists():
                self.log("volume_calculator.py not found", "WARNING")
                self.log("Falling back to original parser", "WARNING")
                self.config.use_improved_parser = False
        
        self.log("Environment check passed", "SUCCESS")
        return True
    
    def step_kmz_parse(self) -> StepResult:
        """Step 1: Parse KMZ/KML file"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 1: KMZ/KML Parsing", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("kmz_parser_agent.py").exists():
            return StepResult(
                step=PipelineStep.KMZ_PARSE,
                success=False,
                message="kmz_parser_agent.py not found"
            )
        
        output_dir = self.config.output_dir / "kmz_output"
        output_dir.mkdir(exist_ok=True)
        
        cmd = [
            "python", "kmz_parser_agent.py",
            str(self.config.input_file),
            "-o", str(output_dir)
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.KMZ_PARSE,
                success=False,
                message=f"KMZ parsing failed: {stderr}"
            )
        
        # Find generated Excel template
        excel_files = list(output_dir.glob("tank_locations_*.xlsx")) + \
                     list(output_dir.glob("tank_locations_*.xls"))
        
        if not excel_files:
            return StepResult(
                step=PipelineStep.KMZ_PARSE,
                success=False,
                message="No Excel template generated from KMZ"
            )
        
        excel_file = excel_files[0]
        self.artifacts["excel_template"] = excel_file
        
        # Find polygon file if any
        polygon_files = list(output_dir.glob("polygon_*.txt"))
        if polygon_files:
            self.artifacts["polygon"] = polygon_files[0]
        
        self.log(f"Generated Excel template: {excel_file}", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.KMZ_PARSE,
            success=True,
            output_file=excel_file,
            message="KMZ parsed successfully",
            data={"excel_template": str(excel_file)}
        )
    
    def step_excel_to_json(self, excel_file: Path) -> StepResult:
        """Step 2: Convert Excel/CSV to JSON"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 2: Excel to JSON Conversion", "INFO")
        self.log("="*60, "INFO")
        
        output_json = self.config.output_dir / "tank_config.json"
        
        # Choose parser based on configuration
        if self.config.use_improved_parser and Path("excel_to_json_improved.py").exists():
            script = "excel_to_json_improved.py"
            self.log("Using improved parser with VolumeCalculator", "INFO")
        else:
            script = "excel_to_json_langgraph.py"
            self.log("Using original parser", "WARNING")
        
        cmd = [
            "python", script,
            str(excel_file),
            "-o", str(output_json)
        ]
        
        if self.config.debug:
            cmd.append("--debug")
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.EXCEL_TO_JSON,
                success=False,
                message=f"Excel to JSON conversion failed: {stderr}"
            )
        
        # Verify JSON was created and is valid
        if not output_json.exists():
            return StepResult(
                step=PipelineStep.EXCEL_TO_JSON,
                success=False,
                message="JSON file not created"
            )
        
        try:
            with open(output_json, 'r') as f:
                data = json.load(f)
                tank_count = len(data.get('tanks', []))
            
            self.artifacts["tank_config"] = output_json
            
            # Analyze volume sources if using improved parser
            volume_sources = {}
            if self.config.use_improved_parser:
                for tank in data.get('tanks', []):
                    src = tank.get('volume_source', 'unknown')
                    volume_sources[src] = volume_sources.get(src, 0) + 1
            
            self.log(f"Converted {tank_count} tanks to JSON", "SUCCESS")
            
            if volume_sources:
                self.log("Volume sources:", "INFO")
                for src, count in volume_sources.items():
                    self.log(f"  - {src}: {count}", "INFO")
            
            return StepResult(
                step=PipelineStep.EXCEL_TO_JSON,
                success=True,
                output_file=output_json,
                message=f"Successfully converted {tank_count} tanks",
                data={
                    "tank_count": tank_count,
                    "volume_sources": volume_sources
                }
            )
            
        except json.JSONDecodeError as e:
            return StepResult(
                step=PipelineStep.EXCEL_TO_JSON,
                success=False,
                message=f"Invalid JSON generated: {e}"
            )
    
    def step_validate_json(self, json_file: Path) -> StepResult:
        """Step 3: Validate JSON structure"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 3: JSON Validation", "INFO")
        self.log("="*60, "INFO")
        
        # Skip if using improved parser (validates internally)
        if self.config.use_improved_parser or self.config.skip_validation:
            self.log("Skipping external validation (internal validation used)", "INFO")
            return StepResult(
                step=PipelineStep.VALIDATE_JSON,
                success=True,
                message="Validation skipped (internal validation)"
            )
        
        if not Path("validate_tank_json.py").exists():
            self.log("validate_tank_json.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.VALIDATE_JSON,
                success=True,
                message="Validator not found, skipping"
            )
        
        cmd = ["python", "validate_tank_json.py", str(json_file)]
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.VALIDATE_JSON,
                success=False,
                message=f"Validation failed: {stderr}"
            )
        
        self.log("JSON validation passed", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.VALIDATE_JSON,
            success=True,
            message="JSON structure validated successfully"
        )
    
    def step_hud_process(self, json_file: Path) -> StepResult:
        """Step 4: Run HUD ASD calculations"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 4: HUD ASD Calculations", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("fast_hud_processor.py").exists():
            self.log("fast_hud_processor.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.HUD_PROCESS,
                success=False,
                message="HUD processor not found"
            )
        
        # HUD processor creates fast_results.json in current directory
        expected_output = Path("fast_results.json")
        output_json = self.config.output_dir / "fast_results.json"
        
        cmd = [
            "python", "fast_hud_processor.py",
            "--config", str(json_file)
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.HUD_PROCESS,
                success=False,
                message=f"HUD processing failed: {stderr}"
            )
        
        # Move the output file to our output directory
        if expected_output.exists():
            import shutil
            shutil.move(str(expected_output), str(output_json))
        elif not output_json.exists():
            return StepResult(
                step=PipelineStep.HUD_PROCESS,
                success=False,
                message="HUD output file not created"
            )
        
        self.artifacts["hud_results"] = output_json
        self.log("HUD ASD calculations completed", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.HUD_PROCESS,
            success=True,
            output_file=output_json,
            message="HUD processing completed"
        )
    
    def step_generate_pdf(self, hud_results: Path) -> StepResult:
        """Step 5: Generate PDF report from screenshots"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 5: PDF Report Generation", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("generate_pdf.py").exists():
            self.log("generate_pdf.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.GENERATE_PDF,
                success=False,
                message="PDF generator not found"
            )
        
        # Check if screenshot directory exists
        screenshot_dir = Path(".playwright-mcp")
        if not screenshot_dir.exists():
            self.log("Screenshot directory not found", "WARNING")
            return StepResult(
                step=PipelineStep.GENERATE_PDF,
                success=False,
                message="No screenshots available for PDF generation"
            )
        
        output_pdf = self.config.output_dir / "HUD_ASD_Results.pdf"
        
        # PDF generator works with screenshots, not JSON
        cmd = [
            "python", "generate_pdf.py",
            "-d", str(screenshot_dir),
            "-o", str(output_pdf),
            "--summary"
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.GENERATE_PDF,
                success=False,
                message=f"PDF generation failed: {stderr}"
            )
        
        self.artifacts["pdf_report"] = output_pdf
        self.log(f"PDF report generated: {output_pdf}", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.GENERATE_PDF,
            success=True,
            output_file=output_pdf,
            message="PDF report generated"
        )
    
    def step_update_excel(self, excel_file: Path, hud_results: Path) -> StepResult:
        """Step 6: Update Excel with ASD results"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 6: Excel Update with ASD Results", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("update_excel_with_results.py").exists():
            self.log("update_excel_with_results.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.UPDATE_EXCEL,
                success=False,
                message="Excel updater not found"
            )
        
        # Convert CSV to Excel if needed (update_excel_with_results.py requires Excel format)
        if excel_file.suffix.lower() == '.csv':
            self.log("Converting CSV to Excel format for updater", "INFO")
            import pandas as pd
            temp_excel = self.config.output_dir / f"{excel_file.stem}.xlsx"
            df = pd.read_csv(excel_file)
            df.to_excel(temp_excel, index=False)
            excel_file = temp_excel
        
        output_excel = self.config.output_dir / "with_hud.xlsx"
        
        cmd = [
            "python", "update_excel_with_results.py",
            str(excel_file),
            str(hud_results),
            "-o", str(output_excel)
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.UPDATE_EXCEL,
                success=False,
                message=f"Excel update failed: {stderr}"
            )
        
        self.artifacts["updated_excel"] = output_excel
        self.log(f"Excel updated with ASD results: {output_excel}", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.UPDATE_EXCEL,
            success=True,
            output_file=output_excel,
            message="Excel updated with ASD results"
        )
    
    def step_calculate_distances(self, json_file: Path, polygon_file: Optional[Path] = None) -> StepResult:
        """Step 7: Calculate distances to polygon boundary"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 7: Distance Calculations", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("calculate_distances.py").exists():
            self.log("calculate_distances.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.CALCULATE_DISTANCES,
                success=False,
                message="Distance calculator not found"
            )
        
        if not polygon_file:
            polygon_file = self.artifacts.get("polygon")
        
        if not polygon_file or not polygon_file.exists():
            self.log("No polygon file available", "WARNING")
            return StepResult(
                step=PipelineStep.CALCULATE_DISTANCES,
                success=False,
                message="Polygon file not available"
            )
        
        output_json = self.config.output_dir / "distances.json"
        
        cmd = [
            "python", "calculate_distances.py",
            str(json_file),
            str(polygon_file),
            "-o", str(output_json)
        ]
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.CALCULATE_DISTANCES,
                success=False,
                message=f"Distance calculation failed: {stderr}"
            )
        
        self.artifacts["distances"] = output_json
        self.log("Distance calculations completed", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.CALCULATE_DISTANCES,
            success=True,
            output_file=output_json,
            message="Distances calculated"
        )
    
    def step_check_compliance(self, excel_file: Path, distances_file: Optional[Path] = None) -> StepResult:
        """Step 8: Check compliance"""
        self.log("\n" + "="*60, "INFO")
        self.log("STEP 8: Compliance Check", "INFO")
        self.log("="*60, "INFO")
        
        if not Path("compliance_checker.py").exists():
            self.log("compliance_checker.py not found", "WARNING")
            return StepResult(
                step=PipelineStep.CHECK_COMPLIANCE,
                success=False,
                message="Compliance checker not found"
            )
        
        output_excel = self.config.output_dir / "final_compliance.xlsx"
        
        cmd = [
            "python", "compliance_checker.py",
            str(excel_file)
        ]
        
        if distances_file and distances_file.exists():
            cmd.extend(["--distances", str(distances_file)])
        else:
            cmd.append("--no-distances")
            self.log("Running compliance check without distances", "WARNING")
        
        cmd.extend(["-o", str(output_excel)])
        
        returncode, stdout, stderr = self.run_command(cmd)
        
        if returncode != 0:
            return StepResult(
                step=PipelineStep.CHECK_COMPLIANCE,
                success=False,
                message=f"Compliance check failed: {stderr}"
            )
        
        self.artifacts["compliance_report"] = output_excel
        self.log(f"Compliance report generated: {output_excel}", "SUCCESS")
        
        return StepResult(
            step=PipelineStep.CHECK_COMPLIANCE,
            success=True,
            output_file=output_excel,
            message="Compliance check completed"
        )
    
    def run(self) -> bool:
        """Execute the complete pipeline"""
        start_time = datetime.now()
        
        self.log("\n" + "="*70, "INFO")
        self.log("   TANK PROCESSING PIPELINE - STARTING", "INFO")
        self.log("="*70, "INFO")
        self.log(f"Input: {self.config.input_file}", "INFO")
        self.log(f"Output: {self.config.output_dir}", "INFO")
        self.log(f"Session: {self.config.session_id}", "INFO")
        self.log(f"Parser: {'Improved (VolumeCalculator)' if self.config.use_improved_parser else 'Original'}", "INFO")
        
        # Check environment first
        if not self.check_environment():
            self.log("Environment check failed. Aborting.", "ERROR")
            return False
        
        # Determine starting point based on input file
        input_ext = self.config.input_file.suffix.lower()
        excel_file = None
        
        try:
            # Step 1: Parse KMZ if needed
            if input_ext in ['.kmz', '.kml']:
                result = self.step_kmz_parse()
                self.results[PipelineStep.KMZ_PARSE] = result
                
                if not result.success:
                    self.log(f"KMZ parsing failed: {result.message}", "ERROR")
                    return False
                
                excel_file = result.output_file
                
                self.log("\n⚠️  Please fill the Excel template with tank measurements", "WARNING")
                self.log("Press Enter when ready to continue...", "WARNING")
                input()
            
            elif input_ext in ['.xlsx', '.xls', '.csv']:
                excel_file = self.config.input_file
            
            else:
                self.log(f"Unsupported file type: {input_ext}", "ERROR")
                return False
            
            # Step 2: Convert Excel to JSON
            result = self.step_excel_to_json(excel_file)
            self.results[PipelineStep.EXCEL_TO_JSON] = result
            
            if not result.success:
                self.log(f"Excel to JSON conversion failed: {result.message}", "ERROR")
                return False
            
            json_file = result.output_file
            
            # Step 3: Validate JSON (optional)
            result = self.step_validate_json(json_file)
            self.results[PipelineStep.VALIDATE_JSON] = result
            
            if not result.success:
                self.log(f"JSON validation failed: {result.message}", "ERROR")
                return False
            
            # Step 4: HUD Processing
            result = self.step_hud_process(json_file)
            self.results[PipelineStep.HUD_PROCESS] = result
            
            if not result.success:
                self.log(f"HUD processing failed: {result.message}", "WARNING")
                # Continue without HUD results
            else:
                hud_results = result.output_file
                
                # Step 5: Generate PDF from screenshots
                result = self.step_generate_pdf(hud_results)
                self.results[PipelineStep.GENERATE_PDF] = result
                if not result.success:
                    self.log(f"PDF generation failed: {result.message}", "WARNING")
                
                # Step 6: Update Excel with HUD results
                result = self.step_update_excel(excel_file, hud_results)
                self.results[PipelineStep.UPDATE_EXCEL] = result
                if not result.success:
                    self.log(f"Excel update failed: {result.message}", "WARNING")
                
                if result.success:
                    excel_file = result.output_file  # Use updated Excel for compliance
            
            # Step 7: Calculate distances (optional)
            polygon_file = self.artifacts.get("polygon")
            if polygon_file:
                result = self.step_calculate_distances(json_file, polygon_file)
                self.results[PipelineStep.CALCULATE_DISTANCES] = result
                distances_file = result.output_file if result.success else None
            else:
                distances_file = None
            
            # Step 8: Check compliance
            if self.artifacts.get("updated_excel"):
                result = self.step_check_compliance(
                    self.artifacts["updated_excel"],
                    distances_file
                )
                self.results[PipelineStep.CHECK_COMPLIANCE] = result
            
            # Calculate execution time
            duration = (datetime.now() - start_time).total_seconds()
            
            # Print summary
            self.print_summary(duration)
            
            return True
            
        except Exception as e:
            self.log(f"Pipeline error: {str(e)}", "ERROR")
            if self.config.debug:
                self.log(traceback.format_exc(), "DEBUG")
            return False
    
    def print_summary(self, duration: float):
        """Print pipeline execution summary"""
        self.log("\n" + "="*70, "INFO")
        self.log("   PIPELINE EXECUTION SUMMARY", "INFO")
        self.log("="*70, "INFO")
        
        # Step results
        self.log("\nStep Results:", "INFO")
        for step in PipelineStep:
            if step in self.results:
                result = self.results[step]
                status = "✅ SUCCESS" if result.success else "❌ FAILED"
                self.log(f"  {step.value:20} : {status}", 
                        "SUCCESS" if result.success else "ERROR")
        
        # Generated artifacts
        self.log("\nGenerated Files:", "INFO")
        for name, path in self.artifacts.items():
            if path and path.exists():
                size = path.stat().st_size
                self.log(f"  - {name}: {path} ({size:,} bytes)", "INFO")
        
        # Statistics
        if PipelineStep.EXCEL_TO_JSON in self.results:
            result = self.results[PipelineStep.EXCEL_TO_JSON]
            if result.data.get("tank_count"):
                self.log(f"\nTank Statistics:", "INFO")
                self.log(f"  Total tanks: {result.data['tank_count']}", "INFO")
                
                if result.data.get("volume_sources"):
                    self.log("  Volume sources:", "INFO")
                    for src, count in result.data["volume_sources"].items():
                        self.log(f"    - {src}: {count}", "INFO")
        
        # Execution time
        self.log(f"\nExecution time: {duration:.2f} seconds", "INFO")
        self.log(f"Log file: {self.log_file}", "INFO")
        
        self.log("\n" + "="*70, "SUCCESS")
        self.log("   PIPELINE COMPLETED SUCCESSFULLY", "SUCCESS")
        self.log("="*70 + "\n", "SUCCESS")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Tank Processing Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Steps:
  1. Parse KMZ/KML (if provided)
  2. Convert Excel/CSV to JSON
  3. Validate JSON structure
  4. Process with HUD calculator
  5. Generate PDF report
  6. Update Excel with results
  7. Calculate distances to boundary
  8. Check compliance

Examples:
  %(prog)s tanks.xlsx
  %(prog)s facility.kmz -o reports/
  %(prog)s tanks.csv --legacy --skip-validation
  %(prog)s data.xlsx --debug
        """
    )
    
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input file (KMZ/KML/Excel/CSV)"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("outputs"),
        help="Output directory (default: outputs)"
    )
    
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Use original parser instead of improved version"
    )
    
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip JSON validation step"
    )
    
    parser.add_argument(
        "--session",
        type=str,
        help="Session ID for tracking"
    )
    
    parser.add_argument(
        "--preserve-columns",
        action="store_true",
        default=True,
        help="Preserve original Excel columns"
    )
    
    parser.add_argument(
        "--normalize-copy",
        action="store_true",
        help="Generate normalized copy of Excel"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.input_file.exists():
        print(f"Error: Input file not found: {args.input_file}")
        return 1
    
    # Create configuration
    config = PipelineConfig(
        input_file=args.input_file.resolve(),
        output_dir=args.output.resolve(),
        use_improved_parser=not args.legacy,
        skip_validation=args.skip_validation,
        debug=args.debug,
        session_id=args.session,
        preserve_columns=args.preserve_columns,
        generate_normalized_copy=args.normalize_copy,
    )
    
    # Run pipeline
    orchestrator = PipelineOrchestrator(config)
    
    try:
        success = orchestrator.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        orchestrator.log("\nPipeline interrupted by user", "WARNING")
        return 130
    except Exception as e:
        orchestrator.log(f"Fatal error: {e}", "ERROR")
        if args.debug:
            import traceback
            orchestrator.log(traceback.format_exc(), "DEBUG")
        return 1


if __name__ == "__main__":
    sys.exit(main())