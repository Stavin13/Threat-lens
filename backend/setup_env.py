#!/usr/bin/env python3
"""
ThreatLens Environment Setup Script

This script helps users set up their environment configuration,
including Groq API key setup and other configuration options.
"""
import os
import shutil
from pathlib import Path


def create_env_file():
    """Create .env file from .env.example if it doesn't exist."""
    env_example_path = Path(".env.example")
    env_path = Path(".env")
    
    if not env_example_path.exists():
        print("❌ .env.example file not found!")
        return False
    
    if env_path.exists():
        print("✅ .env file already exists")
        return True
    
    # Copy .env.example to .env
    shutil.copy(env_example_path, env_path)
    print("✅ Created .env file from .env.example")
    return True


def get_groq_api_key():
    """Get Groq API key from user input."""
    print("\n🔑 Groq API Key Setup")
    print("=" * 50)
    print("To use AI-powered analysis, you need a free Groq API key.")
    print("1. Visit: https://console.groq.com/keys")
    print("2. Sign up for a free account")
    print("3. Create a new API key")
    print("4. Copy the API key")
    print()
    
    api_key = input("Enter your Groq API key (or press Enter to skip): ").strip()
    
    if not api_key:
        print("⚠️  Skipping Groq API key setup. You can add it later to the .env file.")
        print("   Without an API key, the system will use rule-based analysis only.")
        return None
    
    return api_key


def update_env_file(api_key=None, model=None):
    """Update .env file with user-provided values."""
    env_path = Path(".env")
    
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    # Read current .env file
    with open(env_path, 'r') as f:
        lines = f.readlines()
    
    # Update lines
    updated_lines = []
    for line in lines:
        if api_key and line.startswith('GROQ_API_KEY='):
            updated_lines.append(f'GROQ_API_KEY={api_key}\n')
        elif model and line.startswith('GROQ_MODEL='):
            updated_lines.append(f'GROQ_MODEL={model}\n')
        else:
            updated_lines.append(line)
    
    # Write updated .env file
    with open(env_path, 'w') as f:
        f.writelines(updated_lines)
    
    print("✅ Updated .env file")
    return True


def choose_model():
    """Let user choose Groq model."""
    print("\n🤖 Model Selection")
    print("=" * 50)
    print("Available Groq models:")
    print("1. llama-3.1-8b-instant (Default - Fast, good for most use cases)")
    print("2. llama-3.1-70b-versatile (Slower but more capable)")
    print("3. mixtral-8x7b-32768 (Good balance of speed and capability)")
    print("4. gemma2-9b-it (Alternative option)")
    print()
    
    choice = input("Choose model (1-4, or press Enter for default): ").strip()
    
    models = {
        '1': 'llama-3.1-8b-instant',
        '2': 'llama-3.1-70b-versatile', 
        '3': 'mixtral-8x7b-32768',
        '4': 'gemma2-9b-it'
    }
    
    if choice in models:
        return models[choice]
    else:
        print("Using default model: llama-3.1-8b-instant")
        return 'llama-3.1-8b-instant'


def create_data_directory():
    """Create data directory for database and reports."""
    data_dir = Path("data")
    reports_dir = data_dir / "reports"
    
    data_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)
    
    print("✅ Created data directories")


def test_groq_connection(api_key):
    """Test Groq API connection."""
    if not api_key:
        return False
    
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        
        # Simple test request
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        
        print("✅ Groq API connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Groq API connection failed: {str(e)}")
        print("   Please check your API key and try again.")
        return False


def main():
    """Main setup function."""
    print("🛡️  ThreatLens Environment Setup")
    print("=" * 50)
    print()
    
    # Step 1: Create .env file
    if not create_env_file():
        return
    
    # Step 2: Get API key
    api_key = get_groq_api_key()
    
    # Step 3: Choose model
    model = None
    if api_key:
        model = choose_model()
    
    # Step 4: Update .env file
    if api_key or model:
        update_env_file(api_key=api_key, model=model)
    
    # Step 5: Create data directories
    create_data_directory()
    
    # Step 6: Test connection
    if api_key:
        print("\n🧪 Testing Groq API Connection")
        print("=" * 50)
        test_groq_connection(api_key)
    
    # Final instructions
    print("\n🎉 Setup Complete!")
    print("=" * 50)
    print("Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Initialize database: python app/init_db.py")
    print("3. Start the application: uvicorn main:app --reload")
    print()
    
    if not api_key:
        print("💡 To enable AI analysis later:")
        print("   1. Get a Groq API key from https://console.groq.com/keys")
        print("   2. Add it to your .env file: GROQ_API_KEY=your_key_here")
        print("   3. Restart the application")
    
    print("\n📖 For more information, see the README.md file")


if __name__ == "__main__":
    main()