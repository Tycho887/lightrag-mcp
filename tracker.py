#!/usr/bin/env python3
import json
import http.server
import socketserver
import threading
import asyncio
import time
import sqlite3
import pathlib

# Imported necessary utilities and database operators
from lib.db import init_db, get_all_repositories, DB_PATH
from lib.util import process_and_register_repository
from lib.processing import process_files_batch

PORT = 8080

class DynamicDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass

    def do_GET(self) -> None:
        if self.path == '/':
            self.path = 'index.html'
            return super().do_GET()
            
        elif self.path == '/api/repositories':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            data = get_all_repositories()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            return super().do_GET()


async def check_and_sync_repositories() -> None:
    """
    Iterates through all tracked repositories, checks the remote origins for updates,
    and updates both the local SQLite state and LightRAG collections.
    """
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting periodic synchronization cycle...")
    
    # 1. Gather all tracked repositories from the database
    repositories = get_all_repositories()
    if not repositories:
        print("No repositories registered for tracking yet.")
        return

    all_changed_files = []

    for repo in repositories:
        repo_url = repo["repo_url"]
        local_path = pathlib.Path(repo["local_path"])
        
        print(f"Checking for updates in: {repo_url}")
        
        # 2. Safely perform a git fetch and pull to update local file states
        if local_path.exists():
            try:
                import subprocess
                # Fetch remote references
                subprocess.run(["git", "fetch"], cwd=str(local_path), check=True, capture_output=True)
                # Pull changes into the tracking branch
                subprocess.run(["git", "pull"], cwd=str(local_path), check=True, capture_output=True)
            except subprocess.SubprocessError as e:
                print(f"Failed to update git repository at {local_path}: {e}")
                continue

        # 3. Analyze the repository files and calculate structural changes
        # This updates the DB metadata and fills tracked_files with 'changed' statuses
        discovered_files = process_and_register_repository(repo_url)

        # 4. Filter out files that were actually modified or added
        # By cross-referencing with the database state updated during process_and_register_repository
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Fetch files that are explicitly flagged as 'changed' or have never been sent to LightRAG
            cursor.execute("""
                SELECT file_path, repo_url, status 
                FROM tracked_files 
                WHERE repo_url = ? AND (status = 'changed' OR processed_text IS NULL)
            """, (repo_url,))
            
            pending_files = [dict(row) for row in cursor.fetchall()]
            all_changed_files.extend(pending_files)

    # 5. Process all gathered updates via the existing batch pipeline
    if all_changed_files:
        print(f"Detected {len(all_changed_files)} files requiring LightRAG synchronization.")
        await process_files_batch(all_changed_files)
    else:
        print("All repositories are completely up to date.")


def run_sync_scheduler_loop() -> None:
    """
    Wrapper function running inside a dedicated thread to manage
    the 5-minute event loop interval execution safely.
    """
    # Create an isolated event loop for this background worker thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Initial delay to give the server startup time to print its ready messages
    time.sleep(5)
    
    INTERVAL_SECONDS = 300  # 5 minutes
    
    while True:
        try:
            loop.run_until_complete(check_and_sync_repositories())
        except Exception as e:
            print(f"Error encountered during background synchronization loop: {e}")
            
        time.sleep(INTERVAL_SECONDS)


def main() -> None:
    init_db()
    
    # Spawn the synchronization loop inside a daemonized worker thread
    sync_thread = threading.Thread(target=run_sync_scheduler_loop, daemon=True)
    sync_thread.start()
    
    with socketserver.TCPServer(("0.0.0.0", PORT), DynamicDashboardHandler) as httpd:
        print(f"Monitoring Dashboard ready at: http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down monitor daemon.")

if __name__ == "__main__":
    main()