import os
import re
import asyncio
import pathlib
from typing import List, Dict, Any
from dotenv import load_dotenv

from openai import AsyncAzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Ensure these match your actual util/db imports
from lib.util import filter_document
# UPDATE: Added mark_file_processed to the imports
from lib.db import mark_file_deleted, mark_file_processed
from lib.lightrag import add_document, remove_document, update_document

load_dotenv()

# ==========================================
# AZURE OPENAI CONFIGURATION
# ==========================================

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://ai.azure.com/.default"
)

# AZURE_ENDPOINT = "https://dave-alpha001-resource.services.ai.azure.com/"
# DEPLOYMENT_NAME = "gpt-4.1-1"
# API_VERSION = "2024-02-15-preview" 

openai_client = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_ENDPOINT"),
    azure_deployment=os.getenv("DEPLOYMENT_NAME"),
    api_version=os.getenv("API_VERSION"),
    azure_ad_token_provider=token_provider
)

# Concurrency limiter
MAX_CONCURRENT_REQUESTS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# ==========================================
# SEMANTIC CHUNKING
# ==========================================

def semantic_chunk_document(file_path: pathlib.Path, max_chars: int = 16000) -> List[str]:
    """
    Splits a document semantically, prioritizing the preservation of code blocks
    and Markdown headers so context is not broken mid-function.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        return []

    pattern = re.compile(r'(```[\s\S]*?```|\n\n+)')
    segments = pattern.split(content)
    
    chunks = []
    current_chunk = ""

    for segment in segments:
        if not segment.strip():
            continue
            
        if len(current_chunk) + len(segment) > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = segment
        else:
            current_chunk += ("\n\n" if current_chunk else "") + segment

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

# ==========================================
# CORE PROCESSING LOGIC
# ==========================================

async def process_single_chunk(chunk: str) -> str:
    """Compresses a single semantic chunk via Azure OpenAI."""
    async with semaphore:
        system_prompt = (
            "You are a code and text extraction pipeline. Strip all HTML, "
            "Markdown boilerplate, and conversational text. Return ONLY raw, "
            "clean text and preserve code blocks exactly as they are. "
            "CRITICAL INSTRUCTION: The input text is a partial chunk of a larger document. "
            "Sentences or code blocks at the very beginning or end may be cut off. "
            "Do NOT attempt to finish, fix, or modify broken sentences or partial words at the boundaries. "
            "Leave the start and end of the text exactly as provided to allow for seamless merging."
        )
        try:
            response = await openai_client.chat.completions.create(
                model=os.getenv("DEPLOYMENT_NAME"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk}
                ],
                temperature=0.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error compressing chunk: {e}")
            return ""

async def process_file(repo_url: str, file_path_str: str, status: str) -> None:
    """Handles the end-to-end processing of a single tracked file."""
    path_obj = pathlib.Path(file_path_str)

    print(f"Processing file: {file_path_str}")

    # 1. Handle Deletions
    if status == 'deleted' or not path_obj.exists():
        await remove_document(header=file_path_str)
        mark_file_deleted(file_path_str)
        return

    # 2. Filter Irrelevant Files
    if not filter_document(path_obj):
        return

    # 3. Semantic Chunking
    chunks = semantic_chunk_document(path_obj)
    if not chunks:
        return

    # 4. Async Compression
    tasks = [process_single_chunk(chunk) for chunk in chunks]
    compressed_chunks = await asyncio.gather(*tasks)
    compressed_text = "\n\n".join([c for c in compressed_chunks if c])

    if not compressed_text:
        return

    # 5. Push to LightRAG
    metadata = {"repo": repo_url, "file_path": file_path_str}
    if status == "changed":
        await update_document(header=file_path_str, content=compressed_text, metadata=metadata)
    else:
        # Assumed status == 'added' or 'unchanged' (initial run)
        await add_document(header=file_path_str, content=compressed_text, metadata=metadata)

    # 6. UPDATE: Mark as processed in the database
    # This records the compressed_text, sets last_processed_at = CURRENT_TIMESTAMP, 
    # and resets the status to 'unchanged'
    mark_file_processed(file_path_str, compressed_text)
    print(f"Successfully processed and marked in DB: {file_path_str}")


async def process_files_batch(files: List[Dict[str, str]]) -> None:
    """Utility to process multiple files concurrently."""
    print(f"Starting batch processing for {len(files)} files...")
    tasks = [
        process_file(f["repo_url"], f["file_path"], f.get("status", "added")) 
        for f in files
    ]
    await asyncio.gather(*tasks)
    print("Batch processing complete.")