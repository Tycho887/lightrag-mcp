import asyncio
from typing import Dict, Any

# Adjust the import path if the project structure differs
from lib.lightrag import add_document, update_document, remove_document

async def run_integration_test() -> None:
    """
    Executes a sequential add, update, and remove operation against the LightRAG server.
    """
    test_header: str = "test_integration_file_001.txt"
    test_initial_content: str = "This is the initial text payload for testing the LightRAG add document functionality."
    test_updated_content: str = "This is the modified text payload, designed to verify the update functionality."
    test_metadata: Dict[str, Any] = {
        "repo": "https://github.com/example/test-repo.git",
        "file_path": "test_integration_file_001.txt",
        "status": "testing"
    }

    print("--- Initiating LightRAG Lifecycle Test ---")

    # Step 1: Add the document
    print(f"\n[Step 1] Adding test document: {test_header}")
    await add_document(
        header=test_header, 
        content=test_initial_content, 
        metadata=test_metadata
    )
    
    # A brief pause to allow the LightRAG server background tasks to index the document
    await asyncio.sleep(3)

    # Step 2: Update the document
    print(f"\n[Step 2] Updating test document: {test_header}")
    await update_document(
        header=test_header, 
        content=test_updated_content, 
        metadata=test_metadata
    )
    
    await asyncio.sleep(3)

    # Step 3: Remove the document
    print(f"\n[Step 3] Removing test document: {test_header}")
    await remove_document(header=test_header)

    print("\n--- LightRAG Lifecycle Test Complete ---")

if __name__ == "__main__":
    try:
        asyncio.run(run_integration_test())
    except KeyboardInterrupt:
        print("\nTest execution interrupted.")
    except Exception as e:
        print(f"\nAn error occurred during testing: {e}")