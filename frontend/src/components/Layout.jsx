import React, { useState } from 'react';
import Sidebar from './Sidebar.jsx';
import Topbar from './Topbar.jsx';

const Layout = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-surface-base text-slate-900">
      <Sidebar mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content — offset by sidebar width on md+ */}
      <div className="flex min-h-screen flex-col md:pl-sidebar">
        <Topbar onToggleSidebar={() => setSidebarOpen(true)} />

        <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto w-full max-w-screen-xl animate-fade-in">
            {children}
          </div>
        </main>

        <footer className="border-t border-slate-100 px-6 py-3 text-center text-2xs text-slate-400">
          Enterprise Compliance Platform &nbsp;·&nbsp; © {new Date().getFullYear()} Capgemini
        </footer>
      </div>
    </div>
  );
};

export default Layout;
