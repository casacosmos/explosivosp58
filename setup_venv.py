#!/usr/bin/env python3
"""
Setup virtual environment and install dependencies
Run this to create a fresh virtual environment with all requirements
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"→ {description}...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(f"  {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Failed: {e.stderr}")
        return False

def main():
    # Get the script directory
    base_dir = Path(__file__).parent
    os.chdir(base_dir)

    venv_path = base_dir / '.venv'

    print("🚀 Tank Compliance Pipeline - Virtual Environment Setup")
    print("=" * 60)

    # Step 1: Create virtual environment
    if venv_path.exists():
        response = input(f"\n⚠️  Virtual environment already exists at {venv_path}\n   Delete and recreate? (y/N): ")
        if response.lower() == 'y':
            import shutil
            print(f"→ Removing existing virtual environment...")
            shutil.rmtree(venv_path)
        else:
            print("→ Using existing virtual environment")

    if not venv_path.exists():
        if not run_command(
            [sys.executable, '-m', 'venv', '.venv'],
            "Creating virtual environment"
        ):
            print("\n❌ Failed to create virtual environment")
            sys.exit(1)

    # Determine the pip path based on OS
    if sys.platform == 'win32':
        pip_path = venv_path / 'Scripts' / 'pip'
        python_path = venv_path / 'Scripts' / 'python'
        activate_cmd = f"{venv_path}\\Scripts\\activate.bat"
        activate_ps = f"{venv_path}\\Scripts\\Activate.ps1"
    else:
        pip_path = venv_path / 'bin' / 'pip'
        python_path = venv_path / 'bin' / 'python'
        activate_cmd = f"source {venv_path}/bin/activate"

    print(f"\n✅ Virtual environment created at: {venv_path}")

    # Step 2: Upgrade pip
    run_command(
        [str(python_path), '-m', 'pip', 'install', '--upgrade', 'pip'],
        "Upgrading pip"
    )

    # Step 3: Install requirements
    requirements_file = base_dir / 'requirements.txt'
    if requirements_file.exists():
        print(f"\n→ Installing requirements from {requirements_file}...")
        if not run_command(
            [str(pip_path), 'install', '-r', 'requirements.txt'],
            "Installing Python packages"
        ):
            print("\n⚠️  Some packages failed to install, but continuing...")
    else:
        print(f"\n⚠️  No requirements.txt found at {requirements_file}")

    # Step 4: Install Playwright browsers
    print("\n→ Installing Playwright browsers...")
    playwright_cmd = venv_path / ('Scripts' if sys.platform == 'win32' else 'bin') / 'playwright'
    run_command(
        [str(playwright_cmd), 'install', 'chromium'],
        "Installing Chromium for screenshots"
    )

    # Step 5: Create activation helper script
    activate_script = base_dir / 'activate.sh'
    if sys.platform != 'win32':
        with open(activate_script, 'w') as f:
            f.write(f"#!/bin/bash\nsource {venv_path}/bin/activate\n")
        os.chmod(activate_script, 0o755)

    # Print success message
    print("\n" + "=" * 60)
    print("✅ Setup complete!")
    print("\n📋 Next steps:")
    print("\n1. Activate the virtual environment:")

    if sys.platform == 'win32':
        print(f"   Command Prompt: {activate_cmd}")
        print(f"   PowerShell:     {activate_ps}")
    else:
        print(f"   {activate_cmd}")
        print(f"   Or use: ./activate.sh")

    print("\n2. Set your OpenAI API key:")
    if sys.platform == 'win32':
        print("   set OPENAI_API_KEY=your-key-here")
    else:
        print("   export OPENAI_API_KEY='your-key-here'")

    print("\n3. Start the backend server:")
    print("   python start_server.py")

    print("\n4. In another terminal, start the frontend:")
    print("   cd frontend")
    print("   npm install")
    print("   npm run dev")

    print("\n💡 Tip: You can also use the following command to start everything:")
    print("   python start_server.py  # Backend on port 8000")
    print("   # Then open http://localhost:5173 for frontend")

if __name__ == "__main__":
    main()