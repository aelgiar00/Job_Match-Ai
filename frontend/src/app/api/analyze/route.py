import sys
import os
from http.server import BaseHTTPRequestHandler
import json

sys.path.append(os.path.dirname(__file__))

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        response_data = {
            "status": "success",
            "message": "Processed successfully via Vercel Python Serverless!"
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))
        return