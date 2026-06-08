import subprocess
import sys

def launch_mcp_proxy():
    """
    Launches the LightRAG MCP server over HTTP so external agents can connect.
    Requires the base LightRAG API server to be running locally.
    """
    
    # Configuration
    mcp_listen_host = "87.60.121.12"  # Expose to the network (VM access)
    mcp_listen_port = "8000"
    mcp_path = "/mcp"
    
    lightrag_host = "localhost"  # Where the base LightRAG API is running
    lightrag_port = "9621"
    
    cmd = [
        # Assuming the package registers 'lightrag_mcp' as a runnable module/script
        sys.executable, "-m", "lightrag_mcp.main",
        "--mcp-transport", "streamable-http",
        "--mcp-host", mcp_listen_host,
        "--mcp-port", mcp_listen_port,
        "--mcp-streamable-http-path", mcp_path,
        "--host", lightrag_host,
        "--port", lightrag_port,
        # "--api-key", "your_api_key_here"  # Uncomment if your LightRAG API is secured
    ]
    
    print("Starting LightRAG MCP Proxy Server...")
    print(f"Agent Connection Endpoint: http://<YOUR_VM_IP>:{mcp_listen_port}{mcp_path}")
    
    try:
        # Run the server and stream output to the console
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\nShutting down the MCP Proxy gracefully.")
    except Exception as e:
        print(f"\nFailed to start the proxy: {e}")

if __name__ == "__main__":
    launch_mcp_proxy()