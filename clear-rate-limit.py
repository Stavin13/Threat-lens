#!/usr/bin/env python3

import sys
import os

# Change to backend directory and add to path
os.chdir('backend')
sys.path.insert(0, os.getcwd())

try:
    print("🔧 Clearing rate limit cache...")
    
    # Import the rate limiter
    from app.realtime.security import get_rate_limiter
    
    rate_limiter = get_rate_limiter()
    
    # Clear all client data
    rate_limiter.clients.clear()
    rate_limiter.suspicious_clients.clear()
    
    print("✅ Rate limit cache cleared!")
    print("🔄 You may need to restart the backend server for changes to take effect")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("⚠️  This is normal if the backend isn't running yet")
    # Don't show full traceback for this common case