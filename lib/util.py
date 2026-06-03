import os
import hashlib
import pathlib
import subprocess
from typing import Dict, Any, List
# Updated import to include delete_repository
from lib.db import upsert_repository, upsert_tracked_files, delete_repository

REPOS_DIR = "repos"

def calculate_file_hash(file_path: pathlib.Path) -> str:
    """Computes a SHA-256 hash string for tracking file state changes."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
    except (OSError, IOError):
        return ""
    return sha256.hexdigest()

def get_git_metadata(repo_path: str) -> Dict[str, str]:
    """Interrogates local git references via subprocess to collect commit metadata."""
    metadata = {"hash": "unknown", "message": "unknown", "tag": ""}
    try:
        metadata["hash"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_path, text=True
        ).strip()
        
        metadata["message"] = subprocess.check_output(
            ["git", "log", "-1", "--pretty=%B"], cwd=repo_path, text=True
        ).strip()
        
        tag_output = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"], 
            cwd=repo_path, capture_output=True, text=True
        )
        if tag_output.returncode == 0:
            metadata["tag"] = tag_output.stdout.strip()
    except subprocess.SubprocessError:
        pass
    return metadata

def process_and_register_repository(repo_url: str) -> list:
    """Clones downstream endpoints, analyzes files, and updates structural tables."""
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    target_path = pathlib.Path(REPOS_DIR) / repo_name
    absolute_local_path = str(target_path.resolve())

    if not target_path.exists():
        os.makedirs(REPOS_DIR, exist_ok=True)
        subprocess.check_call(["git", "clone", repo_url, str(target_path)])

    git_meta = get_git_metadata(absolute_local_path)
    
    file_records: List[Dict[str, str]] = []
    excluded_extensions = {'.png', '.jpg', '.jpeg', '.pdf', '.lock', '.json', '.git'}
    
    for root, dirs, files in os.walk(absolute_local_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            f_path = pathlib.Path(root) / file
            if f_path.suffix not in excluded_extensions:
                file_records.append({
                    "path": str(f_path.resolve()),
                    "hash": calculate_file_hash(f_path)
                })

    repo_meta = {
        "repo_url": repo_url,
        "local_path": absolute_local_path,
        "hash": git_meta["hash"],
        "file_count": len(file_records),
        "message": git_meta["message"],
        "tag": git_meta["tag"]
    }

    upsert_repository(repo_meta)
    upsert_tracked_files(repo_url, git_meta["hash"], file_records)
    print(f"Successfully processed and indexed repository data structure: {repo_url}")

    # Map internal file records to the format expected by the processing pipeline
    discovered_files = [
        {
            "repo_url": repo_url,
            "file_path": record["path"],
            "status": "added"
        }
        for record in file_records
    ]

    return discovered_files

def remove_and_cleanup_repository(repo_url: str) -> bool:
    """
    Orchestrates repository removal by purging database records and 
    prompting manual cleanup of local filesystem assets.
    """
    repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
    success = delete_repository(repo_url)
    
    if success:
        print(f"Successfully untracked and purged historical data for: {repo_url}")
        print("\n[ACTION REQUIRED] Manual cleanup of local files is required.")
        print(f"Run the following command to delete the repository files:")
        print(f"    rm -rf {REPOS_DIR}/{repo_name}\n")
    else:
        print(f"[Warning] No active tracking records found matching URL: {repo_url}")
        
    return success

def filter_document(file_path: pathlib.Path) -> bool:
    """
    Evaluates whether a document contains valuable text or code information.
    Excludes binaries, compiled assets, styles, and config boilerplate.
    """
    excluded_extensions = {
        '.png', '.jpg', '.jpeg', '.pdf', '.lock', '.json', 
        '.css', '.scss', '.js', '.map', '.ttf', '.woff', '.ico',
        '.exe', '.dll', '.so', '.dylib', '.bin'
    }
    
    excluded_filenames = {
        '.gitignore', '.dockerignore', 'package-lock.json', 'yarn.lock'
    }

    if file_path.suffix.lower() in excluded_extensions:
        return False
        
    if file_path.name in excluded_filenames:
        return False
        
    return True

def chunk_document(file_path: pathlib.Path) -> List[str]:
    """
    Splits the raw document into semantic chunks using a deterministic 
    sliding window to avoid breaking words.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return []

    CHUNK_SIZE_CHARS = 16000 
    chunks = []
    
    start = 0
    content_length = len(content)

    while start < content_length:
        # If the remaining text fits in one chunk, take it all
        if content_length - start <= CHUNK_SIZE_CHARS:
            chunks.append(content[start:])
            break
            
        # Define the maximum window for this chunk
        window = content[start:start + CHUNK_SIZE_CHARS]
        
        # 1. Prefer splitting at double newlines (paragraphs)
        break_idx = window.rfind('\n\n')
        
        # 2. Fallback to single newline (lines)
        if break_idx == -1:
            break_idx = window.rfind('\n')
            
        # 3. Fallback to a space character (words)
        if break_idx == -1:
            break_idx = window.rfind(' ')
            
        # 4. Absolute fallback: hard break (e.g., long unbroken strings/base64)
        if break_idx == -1:
            break_idx = CHUNK_SIZE_CHARS - 1
            
        # Include the boundary character in the current chunk
        end = start + break_idx + 1 
        chunks.append(content[start:end])
        
        # Advance the start pointer
        start = end

    return chunks