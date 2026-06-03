import os
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

LIGHTRAG_SERVER_URL = os.getenv("LIGHTRAG_SERVER_URL")

async def add_document(header: str, content: str, metadata: Dict[str, Any]) -> None:
    """
    Uploads a new document to the LightRAG server using the text insertion endpoint.
    """
    endpoint = f"{LIGHTRAG_SERVER_URL}/documents/text"
    
    payload = {
        "file_source": header,
        "text": content
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, json=payload, timeout=60.0)
            response.raise_for_status()
            print(f"Successfully added to LightRAG: {header}")
        except httpx.HTTPStatusError as e:
            print(f"HTTP error adding document {header}: {e.response.text}")
        except Exception as e:
            print(f"Connection error adding document {header}: {e}")

async def remove_document(header: str) -> None:
    """
    Removes an existing document and its associated graph entities from the LightRAG server.
    """
    endpoint = f"{LIGHTRAG_SERVER_URL}/documents/delete_document"
    
    # Updated payload to match the expected schema
    payload = {
        "doc_ids": [header],
        "delete_file": False,
        "delete_llm_cache": False
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request("DELETE", endpoint, json=payload, timeout=60.0)
            response.raise_for_status()
            print(f"Successfully removed from LightRAG: {header}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                print(f"Document not found on server, skipping removal: {header}")
            else:
                print(f"HTTP error removing document {header}: {e.response.text}")
        except Exception as e:
            print(f"Connection error removing document {header}: {e}")

async def update_document(header: str, content: str, metadata: Dict[str, Any]) -> None:
    """
    Updates an existing document by explicitly removing the prior graph data 
    and inserting the new file instance.
    """
    print(f"Updating in LightRAG: {header}")
    await remove_document(header)
    await add_document(header, content, metadata)