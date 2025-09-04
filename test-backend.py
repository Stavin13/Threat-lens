#!/usr/bin/env python3

import sys
import os
sys.path.append('backend')

try:
    print("🔍 Testing backend imports...")
    from main import app
    print("✅ Main app imported successfully")
    
    print("🔍 Testing database connection...")
    from app.database import check_database_health
    health = check_database_health()
    print(f"✅ Database health: {health}")
    
    print("🔍 Testing API endpoints...")
    import uvicorn
    print("✅ uvicorn available")
    
    print("🚀 Starting server on http://localhost:8000")
    print("📖 API docs will be available at http://localhost:8000/docs")
    print("🛑 Press Ctrl+C to stop")
    
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()