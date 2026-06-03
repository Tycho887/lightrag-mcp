import sqlite3
from typing import List, Dict, Any

DB_PATH = "repo_sync_state.db"

def init_db() -> None:
    """Creates the necessary database tables if they do not exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repositories (
                repo_url TEXT PRIMARY KEY,
                local_path TEXT NOT NULL,
                latest_commit_hash TEXT NOT NULL,
                last_checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_count INTEGER DEFAULT 0,
                latest_commit_message TEXT,
                latest_version_tag TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracked_files (
                file_path TEXT PRIMARY KEY,
                repo_url TEXT,
                last_commit_hash TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                status TEXT DEFAULT 'unchanged',
                processed_text TEXT,
                last_processed_at TIMESTAMP,
                FOREIGN KEY(repo_url) REFERENCES repositories(repo_url)
            )
        """)
        conn.commit()

def upsert_repository(repo_meta: Dict[str, Any]) -> None:
    """Inserts or updates a tracked repository record."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO repositories (
                repo_url, local_path, latest_commit_hash, 
                file_count, latest_commit_message, latest_version_tag, last_checked_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_url) DO UPDATE SET
                latest_commit_hash=excluded.latest_commit_hash,
                file_count=excluded.file_count,
                latest_commit_message=excluded.latest_commit_message,
                latest_version_tag=excluded.latest_version_tag,
                last_checked_at=CURRENT_TIMESTAMP
        """, (
            repo_meta["repo_url"], repo_meta["local_path"], repo_meta["hash"],
            repo_meta["file_count"], repo_meta["message"], repo_meta["tag"]
        ))
        conn.commit()

def upsert_tracked_files(repo_url: str, commit_hash: str, file_records: List[Dict[str, str]]) -> None:
    """Updates database records, calculating changed status via hash comparison."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        for record in file_records:
            cursor.execute("""
                INSERT INTO tracked_files (file_path, repo_url, last_commit_hash, file_hash, status)
                VALUES (?, ?, ?, ?, 'unchanged')
                ON CONFLICT(file_path) DO UPDATE SET
                    status = CASE WHEN file_hash != excluded.file_hash THEN 'changed' ELSE 'unchanged' END,
                    last_commit_hash=excluded.last_commit_hash,
                    file_hash=excluded.file_hash
            """, (record["path"], repo_url, commit_hash, record["hash"]))
        conn.commit()

def delete_repository(repo_url: str) -> bool:
    """
    Removes all tracked files and the repository entry from the database.
    Returns True if a repository was found and deleted, False otherwise.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracked_files WHERE repo_url = ?", (repo_url,))
        cursor.execute("DELETE FROM repositories WHERE repo_url = ?", (repo_url,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_repositories() -> List[Dict[str, Any]]:
    """Fetches all repository metadata records for the API layer."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM repositories ORDER BY last_checked_at DESC")
        return [dict(row) for row in cursor.fetchall()]

def get_files_pending_processing() -> List[Dict[str, Any]]:
    """Fetches files that are new or have been modified and need LLM processing."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Fetch files that are marked as changed, or have no processed text yet
        cursor.execute("""
            SELECT file_path, repo_url, status 
            FROM tracked_files 
            WHERE status = 'changed' OR processed_text IS NULL
        """)
        return [dict(row) for row in cursor.fetchall()]

def mark_file_processed(file_path: str, processed_text: str) -> None:
    """Updates the database with the compressed text and resets the status."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tracked_files 
            SET processed_text = ?, 
                last_processed_at = CURRENT_TIMESTAMP,
                status = 'unchanged'
            WHERE file_path = ?
        """, (processed_text, file_path))
        conn.commit()

def mark_file_deleted(file_path: str) -> None:
    """Removes a file from the tracking database entirely."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracked_files WHERE file_path = ?", (file_path,))
        conn.commit()