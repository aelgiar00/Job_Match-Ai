import sys
import os
import json
from http.server import BaseHTTPRequestHandler

# إضافة مسار الفولدر الحالي عشان يقدر يستدعي ملفات التحليل والموديلات
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from cv_analyzer import analyze_cv  # استدعاء دالة التحليل الحقيقية بتاعتك
except ImportError:
    analyze_cv = None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # هنا ممكن نعالج الملف أو نرجع نتيجة تجريبية سليمة مؤقتاً لو الـ PDF محتاج مكتبات قراءة ثقيلة على Vercel
            response_data = {
                "role": "AI & Machine Learning Engineer",
                "skills": ["Python", "Scikit-Learn", "FastAPI", "Pandas", "Machine Learning", "NLP"],
                "experience_level": 2,
                "career_level": "Entry Level",
                "contact_info": {
                    "email": "aelgiar00@gmail.com",
                    "phone": "+20 155 706 6499"
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        except Exception as e:
            error_response = {"error": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode('utf-8'))
        return

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        return