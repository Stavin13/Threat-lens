#!/usr/bin/env python3

import sys
import os
sys.path.append('backend')

from groq import Groq
import json

# Test Groq API connection
def test_groq_api():
    print("🔍 Testing Groq API Connection")
    print("=" * 40)
    
    # Get API key from environment
    api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        print("❌ No Groq API key found")
        return False
    
    print(f"✅ API Key found: {api_key[:20]}...")
    
    try:
        # Initialize Groq client
        client = Groq(api_key=api_key)
        print("✅ Groq client initialized")
        
        # Test API call
        print("🔄 Testing API call...")
        
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a cybersecurity expert. Respond only with valid JSON."
                },
                {
                    "role": "user", 
                    "content": """Analyze this security log event and respond with JSON:

Event: Failed password for invalid user admin from 192.168.1.100 port 22 ssh2
Source: sshd
Category: auth

Respond with JSON containing:
- severity_score (1-10)
- explanation (brief)
- recommendations (array of 2-3 items)"""
                }
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        print("✅ API call successful!")
        
        # Parse response
        result = json.loads(response.choices[0].message.content)
        print("\n📊 Analysis Result:")
        print(f"   Severity: {result.get('severity_score', 'N/A')}")
        print(f"   Explanation: {result.get('explanation', 'N/A')}")
        print(f"   Recommendations: {len(result.get('recommendations', []))} items")
        
        print(f"\n🔍 Full Response:")
        print(json.dumps(result, indent=2))
        
        return True
        
    except Exception as e:
        print(f"❌ API call failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_groq_api()
    if success:
        print("\n🎉 Groq API is working correctly!")
    else:
        print("\n❌ Groq API test failed!")
        sys.exit(1)