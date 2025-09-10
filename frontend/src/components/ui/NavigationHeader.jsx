import React, { useState } from 'react';
import { useLocation, Link } from 'react-router-dom';
import Icon from '../AppIcon';
import MobileNavigationMenu from './MobileNavigationMenu';
import ConnectionStatusIndicator from './ConnectionStatusIndicator';

const NavigationHeader = ({ connectionStatus = { connected: true, lastUpdate: new Date() } }) => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', path: '/security-dashboard', icon: 'LayoutDashboard' },
    { id: 'events', label: 'Events', path: '/events-management', icon: 'List' },
    { id: 'ingest', label: 'Ingest', path: '/log-ingestion', icon: 'Upload' },
    { id: 'system', label: 'System', path: '/system-monitoring', icon: 'Server' },
  ];

  const isActiveRoute = (path) => {
    return location?.pathname === path;
  };

  const handleMobileMenuToggle = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  const handleMobileMenuClose = () => {
    setIsMobileMenuOpen(false);
  };

  return (
    <>
      <header className="fixed top-0 left-0 right-0 z-[1000] bg-card border-b border-border shadow-elevation-1">
        <div className="flex items-center justify-between h-16 px-4">
          {/* Logo Section */}
          <div className="flex items-center">
            <Link to="/security-dashboard" className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-8 h-8 bg-primary rounded-md">
                <Icon name="Shield" size={20} color="white" strokeWidth={2.5} />
              </div>
              <span className="text-xl font-semibold text-foreground">ThreatLens</span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            {menuItems?.map((item) => (
              <Link
                key={item?.id}
                to={item?.path}
                className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-micro min-h-touch ${
                  isActiveRoute(item?.path)
                    ? 'bg-primary text-primary-foreground shadow-elevation-2'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                <Icon name={item?.icon} size={18} />
                <span>{item?.label}</span>
              </Link>
            ))}
          </nav>

          {/* Right Section */}
          <div className="flex items-center space-x-4">
            <ConnectionStatusIndicator status={connectionStatus} />
            
            {/* Mobile Menu Button */}
            <button
              onClick={handleMobileMenuToggle}
              className="md:hidden flex items-center justify-center w-10 h-10 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-micro min-h-touch min-w-touch"
              aria-label="Toggle mobile menu"
            >
              <Icon name={isMobileMenuOpen ? 'X' : 'Menu'} size={20} />
            </button>
          </div>
        </div>
      </header>
      {/* Mobile Navigation Menu */}
      <MobileNavigationMenu
        isOpen={isMobileMenuOpen}
        onClose={handleMobileMenuClose}
        menuItems={menuItems}
        currentPath={location?.pathname}
      />
    </>
  );
};

export default NavigationHeader;