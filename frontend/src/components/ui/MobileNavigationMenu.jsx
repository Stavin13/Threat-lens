import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import Icon from '../AppIcon';

const MobileNavigationMenu = ({ isOpen, onClose, menuItems, currentPath }) => {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const handleBackdropClick = (e) => {
    if (e?.target === e?.currentTarget) {
      onClose();
    }
  };

  const handleLinkClick = () => {
    onClose();
  };

  const isActiveRoute = (path) => {
    return currentPath === path;
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[1100] md:hidden"
      onClick={handleBackdropClick}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50 transition-opacity duration-300" />
      {/* Menu Panel */}
      <div className="absolute top-0 right-0 h-full w-80 max-w-[85vw] bg-card shadow-elevation-4 transform transition-transform duration-300">
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-border">
            <div className="flex items-center space-x-3">
              <div className="flex items-center justify-center w-8 h-8 bg-primary rounded-md">
                <Icon name="Shield" size={20} color="white" strokeWidth={2.5} />
              </div>
              <span className="text-lg font-semibold text-foreground">ThreatLens</span>
            </div>
            <button
              onClick={onClose}
              className="flex items-center justify-center w-10 h-10 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-micro min-h-touch min-w-touch"
              aria-label="Close menu"
            >
              <Icon name="X" size={20} />
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="flex-1 p-4">
            <div className="space-y-2">
              {menuItems?.map((item) => (
                <Link
                  key={item?.id}
                  to={item?.path}
                  onClick={handleLinkClick}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-md text-base font-medium transition-micro min-h-touch ${
                    isActiveRoute(item?.path)
                      ? 'bg-primary text-primary-foreground shadow-elevation-2'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                  }`}
                >
                  <Icon name={item?.icon} size={20} />
                  <span>{item?.label}</span>
                </Link>
              ))}
            </div>
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-border">
            <div className="text-xs text-muted-foreground text-center">
              ThreatLens Security Platform
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MobileNavigationMenu;