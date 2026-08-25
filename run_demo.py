"""
OmniGuard AI: Control Plane & Gateway Launcher
"""
import sys
import os
import uvicorn

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

if __name__ == "__main__":
    print("=================================================================")
    print("[*] OmniGuard AI: Enterprise Responsible AI Control Plane (v2.0)")
    print("=================================================================")
    print("Starting FastAPI Gateway and Control Plane Dashboard...")
    print("Local Dashboard URL: http://localhost:8000")
    print("API Endpoint:        http://localhost:8000/api/evaluate")
    print("OpenAI Proxy:        http://localhost:8000/v1/chat/completions")
    print("=================================================================\n")
    
    uvicorn.run("app.server:app", host="0.0.0.0", port=8000, reload=False)
