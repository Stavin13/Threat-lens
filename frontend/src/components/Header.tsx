import React from 'react';

interface HeaderProps {
  title?: string;
}

const Header: React.FC<HeaderProps> = ({ title = 'ThreatLens' }) => {
  return (
    <header className="bg-gray-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <h1 className="text-2xl font-bold text-blue-400">{title}</h1>
            </div>
            <div className="hidden md:block ml-10">
              <div className="flex items-baseline space-x-4">
                <span className="text-gray-300 text-sm">
                  AI-Powered Security Log Analysis
                </span>
              </div>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="text-sm text-gray-300">
              {new Date().toLocaleDateString()}
            </div>
            <div className="w-3 h-3 bg-green-400 rounded-full" title="System Online"></div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;