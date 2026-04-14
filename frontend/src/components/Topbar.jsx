import React, { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { Bell, Search, Menu, ChevronDown, LogOut } from 'lucide-react';

const Topbar = ({ onToggleSidebar }) => {
  const { user, logout } = useContext(UserContext);
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur-md shadow-sm">
      <div className="mx-auto flex h-20 items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            className="inline-flex h-11 w-11 items-center justify-center rounded-3xl border border-slate-200 bg-white text-slate-700 shadow-sm transition duration-200 hover:border-slate-300 hover:text-slate-900 md:hidden"
          >
            <Menu size={18} />
          </button>

          <div className="hidden items-center gap-3 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-3 shadow-sm md:flex">
            <Search size={18} className="text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search dashboards..."
              className="w-64 border-0 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            className="inline-flex h-11 items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 text-sm text-slate-700 shadow-sm transition duration-200 hover:border-slate-300 hover:text-slate-900"
          >
            <Bell size={18} className="text-slate-500" />
            <span className="hidden sm:inline">Notifications</span>
          </button>

          <div className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((prev) => !prev)}
              className="inline-flex items-center gap-3 rounded-3xl border border-slate-200 bg-white px-4 py-3 shadow-sm transition duration-200 hover:border-slate-300"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-600 text-white shadow-sm">
                {user?.username?.charAt(0) || 'A'}
              </div>
              <div className="hidden text-left sm:block">
                <p className="text-sm font-semibold text-slate-900">{user?.username}</p>
                <p className="text-xs uppercase tracking-[0.2em] text-sky-600">{user?.role}</p>
              </div>
              <ChevronDown size={18} className="text-slate-500" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 z-50 mt-3 w-56 rounded-[1.75rem] border border-slate-200 bg-white p-3 shadow-2xl">
                <div className="mb-3 rounded-3xl bg-slate-50 px-4 py-4 text-sm">
                  <p className="font-semibold text-slate-900">{user?.username}</p>
                  <p className="text-xs uppercase tracking-[0.2em] text-sky-600">{user?.role}</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center justify-between rounded-3xl border border-slate-200 bg-slate-100 px-4 py-3 text-sm font-semibold text-slate-900 transition duration-200 hover:bg-slate-200"
                >
                  <span>Sign out</span>
                  <LogOut size={16} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;
