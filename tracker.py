#!/usr/bin/env python3
import json
import http.server
import socketserver
from lib.db import init_db, get_all_repositories

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
            # Completely eliminate browser CORS constraints through the network channel directly
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Fetch directly from SQLite live on request
            data = get_all_repositories()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        else:
            return super().do_GET()

def main() -> None:
    init_db()
    with socketserver.TCPServer(("0.0.0.0", PORT), DynamicDashboardHandler) as httpd:
        print(f"Monitoring Dashboard ready at: http://localhost:{PORT}")
        try:
            # Here, an asynchronous scheduler block can be integrated to check for repository updates
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down monitor daemon.")

if __name__ == "__main__":
    main()