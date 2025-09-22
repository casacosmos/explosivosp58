#!/usr/bin/env python3
"""
Start the backend server using system environment variables.
No .env files, no bash scripts - pure Python.

Usage:
    # Set environment variable first:
    export OPENAI_API_KEY="your-key-here"

    # Then run:
    python start_server.py
"""

import os
import sys
import uvicorn
from pathlib import Path

def check_requirements():
    """Check that required environment variables are set"""
    api_key = os.environ.get('OPENAI_API_KEY')

    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable is not set")
        print("\nTo set it:")
        print("  Linux/Mac: export OPENAI_API_KEY='your-key-here'")
        print("  Windows:   set OPENAI_API_KEY=your-key-here")
        print("  Windows PS: $env:OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    print(f"✓ OPENAI_API_KEY is set ({len(api_key)} characters)")
    return True

def start_server():
    """Start the FastAPI server using uvicorn"""
    # Get configuration from environment variables
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', '8000'))
    reload = os.environ.get('RELOAD', 'true').lower() == 'true'
    workers = int(os.environ.get('WORKERS', '1'))

    print(f"\n🚀 Starting Tank Compliance Pipeline Backend")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Reload: {reload}")
    print(f"   Workers: {workers}")
    print(f"\n📚 API Documentation: http://localhost:{port}/docs")
    print(f"🌐 Frontend should connect to: http://localhost:{port}")
    print("\nPress CTRL+C to stop the server\n")

    # Start uvicorn
    uvicorn.run(
        "api.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=1 if reload else workers,  # Can't use multiple workers with reload
        log_level="info"
    )

if __name__ == "__main__":
    # Check requirements
    check_requirements()

    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Start server
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n\n✋ Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)