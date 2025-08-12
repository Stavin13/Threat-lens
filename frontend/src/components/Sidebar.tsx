import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface SidebarItem {
  name: string;
  path: string;
  icon: string;
}

const sidebarItems: SidebarItem[] = [
  { name: 'Dashboard', path: '/', icon: '📊' },
  { name: 'Events', path: '/events', icon: '🔍' },
  { name: 'Reports', path: '/reports', icon: '📄' },
  { name: 'Ingest Logs', path: '/ingest', icon: '📥' },
  { name: 'Configuration', path: '/config', icon: '⚙️' },
];

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onToggle }) => {
  const location = useLocation();

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-gray-600 bg-opacity-75 z-20 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-30 w-64 bg-gray-800 transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between h-16 px-4 bg-gray-900">
          <span className="text-white font-semibold">Navigation</span>
          <button
            onClick={onToggle}
            className="text-gray-400 hover:text-white lg:hidden"
          >
            <span className="sr-only">Close sidebar</span>
            ✕
          </button>
        </div>

        <nav className="mt-5 px-2">
          <div className="space-y-1">
            {sidebarItems.map((item) => {
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.name}
                  to={item.path}
                  className={`group flex items-center px-2 py-2 text-sm font-medium rounded-md transition-colors duration-150 ${
                    isActive
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                  }`}
                  onClick={() => {
                    // Close sidebar on mobile after navigation
                    if (window.innerWidth < 1024) {
                      onToggle();
                    }
                  }}
                >
                  <span className="mr-3 text-lg">{item.icon}</span>
                  {item.name}
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Status section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gray-900">
          <div className="text-xs text-gray-400">
            <div className="flex items-center justify-between">
              <span>System Status</span>
              <span className="text-green-400">Online</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default Sidebar;