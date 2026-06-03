#!/usr/bin/env python3
import argparse
import asyncio
import sqlite3
# Added DB_PATH to imports
from lib.db import init_db, DB_PATH
from lib.util import process_and_register_repository, remove_and_cleanup_repository
# Import the new processing module functions
from lib.processing import process_files_batch#, process_file

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manual Git Repository Ingestion and Removal Utility Interface"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--add-repo", 
        type=str, 
        metavar="URL",
        help="Git target clone endpoint URL to add/update tracking."
    )
    group.add_argument(
        "--remove-repo", 
        type=str, 
        metavar="URL",
        help="Git target clone endpoint URL to remove from database tracking."
    )
    
    args = parser.parse_args()
    init_db()

    if args.add_repo:
        print(f"Initiating registration pipeline for: {args.add_repo}")
        
        discovered_files = process_and_register_repository(args.add_repo)
        
        if discovered_files:
            # Trigger the inline processing pipeline asynchronously
            asyncio.run(process_files_batch(discovered_files))
        else:
            print("No valid files found to process during ingestion.")
            
    elif args.remove_repo:
        print(f"Initiating removal pipeline for: {args.remove_repo}")
        
        # 1. Fetch files to delete from LightRAG *before* removing DB records
        files_to_delete = []
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path FROM tracked_files WHERE repo_url = ?", 
                (args.remove_repo,)
            )
            for row in cursor.fetchall():
                files_to_delete.append({
                    "repo_url": args.remove_repo,
                    "file_path": row[0],
                    "status": "deleted"
                })

        # 2. Trigger the LightRAG deletion pipeline via the processing module
        if files_to_delete:
            print(f"Purging {len(files_to_delete)} files from the LightRAG server...")
            asyncio.run(process_files_batch(files_to_delete))
        else:
            print("No active documents found in the vector database to purge.")

        # 3. Clean up the local SQLite database and display local FS instructions
        remove_and_cleanup_repository(args.remove_repo)

if __name__ == "__main__":
    main()