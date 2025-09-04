#!/bin/bash

echo "🧪 Testing ThreatLens Frontend Integration..."

# Check if we're in the right directory
if [ ! -f "frontend/package.json" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

cd frontend

echo "📦 Installing dependencies..."
npm install --legacy-peer-deps --silent

echo "🔨 Building frontend..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Frontend build successful!"
    echo "🚀 Frontend is ready to run with: npm run dev"
    echo "🌐 Will be available at: http://localhost:3000"
else
    echo "❌ Frontend build failed"
    exit 1
fi

cd ..
echo "✅ Frontend integration test completed successfully!"