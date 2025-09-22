#!/usr/bin/env python3
"""
Reorganize output files into a cleaner session-based structure
"""
import os
import shutil
from pathlib import Path
import json
from datetime import datetime


def organize_session_outputs(session_id: str, work_dir: Path = Path("work")):
    """
    Reorganize outputs for a specific session into a structured directory layout

    New structure:
    work/{session_id}/
    ├── state.json          # Session state
    ├── datastore.json      # Tank data backbone
    ├── uploads/           # User uploaded files
    ├── screenshots/       # HUD screenshots
    ├── exports/          # Generated files
    │   ├── excel/       # Excel files
    │   ├── json/        # JSON configs
    │   ├── pdf/         # PDF reports
    │   └── compliance/  # Compliance reports
    └── logs/            # Processing logs
    """

    session_path = work_dir / session_id
    if not session_path.exists():
        print(f"Session {session_id} not found")
        return False

    # Create organized directory structure
    dirs = {
        'uploads': session_path / 'uploads',
        'screenshots': session_path / 'screenshots',
        'exports': session_path / 'exports',
        'excel': session_path / 'exports' / 'excel',
        'json': session_path / 'exports' / 'json',
        'pdf': session_path / 'exports' / 'pdf',
        'compliance': session_path / 'exports' / 'compliance',
        'logs': session_path / 'logs'
    }

    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)

    # Move files to appropriate locations
    moves = []

    # Move existing files based on extensions and patterns
    for file in session_path.glob("*"):
        if file.is_file():
            name = file.name.lower()

            # Skip already organized files
            if file.parent.name in ['uploads', 'screenshots', 'exports', 'logs']:
                continue

            # Categorize and move files
            if name.endswith('.xlsx') or name.endswith('.xls'):
                if 'template' in name or 'locations' in name:
                    dest = dirs['excel'] / file.name
                elif 'compliance' in name or 'final' in name:
                    dest = dirs['compliance'] / file.name
                else:
                    dest = dirs['excel'] / file.name

            elif name.endswith('.json'):
                if name == 'state.json' or name == 'datastore.json':
                    continue  # Keep in root
                dest = dirs['json'] / file.name

            elif name.endswith('.pdf'):
                dest = dirs['pdf'] / file.name

            elif name.endswith('.png') or name.endswith('.jpg'):
                dest = dirs['screenshots'] / file.name

            elif name.endswith('.kmz') or name.endswith('.kml'):
                dest = dirs['uploads'] / file.name

            elif name.endswith('.log') or name.endswith('.txt'):
                if 'log' in name:
                    dest = dirs['logs'] / file.name
                else:
                    dest = dirs['uploads'] / file.name
            else:
                continue

            if dest != file:
                shutil.move(str(file), str(dest))
                moves.append((file.name, dest))
                print(f"  Moved: {file.name} → {dest.relative_to(session_path)}")

    # Update state.json with new paths
    state_file = session_path / 'state.json'
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())

            # Update paths in state
            path_updates = {}
            for key, value in state.items():
                if isinstance(value, str) and session_id in value:
                    # Check if file was moved
                    old_path = Path(value)
                    if old_path.exists():
                        continue  # File still in original location

                    # Find new location
                    filename = old_path.name
                    for moved_from, moved_to in moves:
                        if moved_from == filename:
                            path_updates[key] = str(moved_to)
                            break

            if path_updates:
                state.update(path_updates)
                state['reorganized_at'] = datetime.utcnow().isoformat()
                state_file.write_text(json.dumps(state, indent=2))
                print(f"  Updated state.json with {len(path_updates)} new paths")

        except Exception as e:
            print(f"  Warning: Could not update state.json: {e}")

    # Create index file
    index = {
        'session_id': session_id,
        'organized_at': datetime.utcnow().isoformat(),
        'structure': {
            'uploads': len(list(dirs['uploads'].glob('*'))),
            'screenshots': len(list(dirs['screenshots'].glob('*'))),
            'excel_exports': len(list(dirs['excel'].glob('*'))),
            'json_configs': len(list(dirs['json'].glob('*'))),
            'pdf_reports': len(list(dirs['pdf'].glob('*'))),
            'compliance': len(list(dirs['compliance'].glob('*'))),
            'logs': len(list(dirs['logs'].glob('*')))
        }
    }

    index_file = session_path / 'index.json'
    index_file.write_text(json.dumps(index, indent=2))

    print(f"\n✅ Session {session_id} organized:")
    for category, count in index['structure'].items():
        if count > 0:
            print(f"   {category}: {count} files")

    return True


def organize_all_sessions(work_dir: Path = Path("work")):
    """Organize all sessions in the work directory"""

    if not work_dir.exists():
        print(f"Work directory {work_dir} not found")
        return

    sessions = [d for d in work_dir.iterdir() if d.is_dir()]

    if not sessions:
        print("No sessions found")
        return

    print(f"Found {len(sessions)} sessions to organize\n")

    for session_dir in sessions:
        session_id = session_dir.name
        print(f"Organizing session: {session_id}")
        organize_session_outputs(session_id, work_dir)
        print()


def cleanup_root_outputs():
    """Move any output files from root to appropriate session directories"""

    root_files = {
        'fast_results.json': 'exports/json',
        'HUD_ASD_Results.pdf': 'exports/pdf',
        'tank_config.json': 'exports/json',
    }

    # Check for files in root that should be in session dirs
    for filename, target_subdir in root_files.items():
        file_path = Path(filename)
        if file_path.exists():
            # Try to determine session from file modification time
            # or move to a 'legacy' session
            legacy_session = Path('work/legacy')
            legacy_session.mkdir(parents=True, exist_ok=True)

            target_dir = legacy_session / target_subdir
            target_dir.mkdir(parents=True, exist_ok=True)

            dest = target_dir / filename
            shutil.move(str(file_path), str(dest))
            print(f"Moved root file {filename} to {dest}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Organize pipeline outputs")
    parser.add_argument('--session', help='Specific session ID to organize')
    parser.add_argument('--all', action='store_true', help='Organize all sessions')
    parser.add_argument('--cleanup-root', action='store_true', help='Clean up root directory files')

    args = parser.parse_args()

    if args.cleanup_root:
        cleanup_root_outputs()
    elif args.session:
        organize_session_outputs(args.session)
    elif args.all:
        organize_all_sessions()
    else:
        # Default: organize all
        organize_all_sessions()