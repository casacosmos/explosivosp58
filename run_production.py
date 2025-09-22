#!/usr/bin/env python3
"""
Production server runner with Gunicorn
Reads all configuration from system environment variables

Usage:
    export OPENAI_API_KEY="your-key-here"
    python run_production.py
"""

import os
import sys
import multiprocessing
from pathlib import Path

def start_gunicorn():
    """Start the server using Gunicorn for production"""

    # Check for API key
    if not os.environ.get('OPENAI_API_KEY'):
        print("ERROR: OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    # Configuration from environment
    host = os.environ.get('HOST', '0.0.0.0')
    port = os.environ.get('PORT', '8000')
    workers = os.environ.get('WORKERS', str(multiprocessing.cpu_count() * 2 + 1))

    # Change to app directory
    app_dir = Path(__file__).parent
    os.chdir(app_dir)

    # Build gunicorn command
    bind_address = f"{host}:{port}"

    print(f"Starting production server on {bind_address} with {workers} workers")

    # Start gunicorn
    os.execvp('gunicorn', [
        'gunicorn',
        'api.main:app',
        '--bind', bind_address,
        '--workers', workers,
        '--worker-class', 'uvicorn.workers.UvicornWorker',
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info'
    ])

if __name__ == '__main__':
    try:
        # Try to import gunicorn
        import gunicorn
    except ImportError:
        print("Gunicorn not installed. Installing...")
        os.system(f"{sys.executable} -m pip install gunicorn")

    start_gunicorn()