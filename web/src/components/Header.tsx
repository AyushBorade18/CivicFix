import { useState } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { Menu, X, ArrowRight } from 'lucide-react';

interface HeaderProps {
  type?: 'citizen' | 'admin';
}

export function Header({ type = 'citizen' }: HeaderProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const citizenNav = [
    { to: '/citizen', label: 'Home', end: true },
    { to: '/citizen/report', label: 'Report a problem' },
    { to: '/citizen/my-reports', label: 'My reports' },
    { to: '/citizen/issues', label: 'Reported problems' },
  ];

  const adminNav = [
    { to: '/admin', label: 'Overview', end: true },
    { to: '/admin/issues', label: 'Issue Explorer' },
    { to: '/admin/map', label: 'Map View' },
    { to: '/admin/works', label: 'Public Works' },
    { to: '/admin/verification', label: 'Verification' },
  ];

  const navItems = type === 'citizen' ? citizenNav : adminNav;

  return (
    <header className="bg-background/95 backdrop-blur-md border-b border-border sticky top-0 z-50 transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5">
        <div className="flex items-center justify-between">
          {/* Brand Logo */}
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="relative w-9 h-9">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl transform rotate-12 transition-transform group-hover:rotate-45 duration-300" />
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl transform -rotate-12 transition-transform group-hover:-rotate-45 duration-300" />
              <div className="absolute inset-0 bg-black rounded-xl flex items-center justify-center shadow-xs">
                <span className="text-white font-bold text-base tracking-tight">W</span>
              </div>
            </div>
            <div className="flex flex-col">
              <span className="text-xl font-bold text-foreground tracking-tight">
                WardSentry
              </span>
              <span className="text-[10px] uppercase font-mono tracking-wider text-secondary -mt-1">
                {type === 'admin' ? 'Admin Console' : 'For the people of Pune'}
              </span>
            </div>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center space-x-6">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `text-sm font-medium transition-colors py-1.5 border-b-2 ${
                    isActive
                      ? 'text-primary border-primary font-semibold'
                      : 'text-secondary border-transparent hover:text-foreground hover:border-border'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* Right Action buttons */}
          <div className="hidden md:flex items-center space-x-3">
            {type === 'citizen' ? (
              <>
                <Link
                  to="/citizen/report"
                  className="btn btn-black text-xs px-4 py-2 rounded-lg font-medium shadow-xs flex items-center gap-1.5"
                >
                  Report a Problem
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/citizen"
                  className="text-xs font-medium text-secondary hover:text-foreground px-3 py-1.5 rounded-lg border border-border/80 hover:bg-muted transition-colors"
                >
                  Citizen View
                </Link>
                <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-200 text-blue-700 text-xs px-2.5 py-1 rounded-full font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                  Pune Ward Engine
                </div>
              </>
            )}
          </div>

          {/* Mobile hamburger button */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg text-secondary hover:text-foreground hover:bg-muted transition-colors"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden pt-3 pb-2 border-t border-border mt-3 space-y-2">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `block px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary/10 text-primary font-semibold'
                      : 'text-secondary hover:bg-muted hover:text-foreground'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
            <div className="pt-2 border-t border-border flex flex-col gap-2">
              {type === 'citizen' ? (
                <>
                  <Link
                    to="/citizen/report"
                    onClick={() => setMobileMenuOpen(false)}
                    className="btn btn-black text-center text-sm"
                  >
                    Report a Problem
                  </Link>
                </>
              ) : (
                <Link
                  to="/citizen"
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-center px-3 py-2 text-sm text-secondary hover:bg-muted rounded-md"
                >
                  Switch to Citizen View
                </Link>
              )}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
export default Header;
