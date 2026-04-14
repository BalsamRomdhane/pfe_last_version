import React, { useContext } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import {
  BarChart3,
  Users,
  Building,
  Settings,
  ShieldCheck,
  X,
} from 'lucide-react';

const Sidebar = ({ mobileOpen, onClose }) => {
  const { user } = useContext(UserContext);
  const location = useLocation();
  const navigationSections = [
    {
      title: 'MAIN',
      items: [
        {
          label: 'Dashboard',
          icon: <BarChart3 size={18} />,
          path: '/dashboard',
          roles: ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'],
        },
      ],
    },
    {
      title: 'MANAGEMENT',
      items: [
        {
          label: 'Users',
          icon: <Users size={18} />,
          path: '/users',
          roles: ['ADMIN'],
        },
        {
          label: 'Departments',
          icon: <Building size={18} />,
          path: '/departments',
          roles: ['ADMIN'],
        },
      ],
    },
    {
      title: 'SYSTEM',
      items: [
        {
          label: 'System',
          icon: <Settings size={18} />,
          path: '/system',
          roles: ['ADMIN'],
        },
      ],
    },
  ];

  const filteredSections = navigationSections.map((section) => ({
    ...section,
    items: section.items.filter((item) => item.roles.includes(user?.role)),
  }));

  return (
    <div>
      <div
        className={`fixed inset-y-0 left-0 top-0 z-40 flex h-screen w-64 transform flex-col overflow-y-auto bg-slate-950 text-slate-100 shadow-2xl transition-transform duration-300 ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className="flex h-full flex-col justify-between overflow-hidden">
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-slate-800 px-6 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-slate-100 text-slate-950 shadow-sm">
                  <ShieldCheck size={20} />
                </div>
                <div>
                  <p className="text-sm font-semibold tracking-wide text-white">Enterprise</p>
                  <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Admin Suite</p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-full bg-white/10 p-2 text-slate-200 transition hover:bg-white/15 md:hidden"
              >
                <X size={18} />
              </button>
            </div>

            <div className="px-4 py-5">
              {filteredSections.map((section) =>
                section.items.length > 0 ? (
                  <div key={section.title} className="mb-6">
                    <div className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500/80">
                      {section.title}
                    </div>
                    <div className="space-y-2">
                      {section.items.map((item) => {
                        const active = location.pathname === item.path;
                        return (
                          <Link
                            key={item.path}
                            to={item.path}
                            onClick={onClose}
                            className={`group flex items-center gap-3 rounded-3xl px-4 py-3 transition-all duration-200 ${
                              active
                                ? 'border-l-4 border-sky-400 bg-slate-800 text-white shadow-lg shadow-slate-950/30'
                                : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                            }`}
                          >
                            <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${active ? 'bg-slate-800' : 'bg-slate-900'}`}>
                              {item.icon}
                            </div>
                            <span className="font-medium">{item.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ) : null
              )}
            </div>
          </div>

          <div className="border-t border-slate-800 p-6">
            <div className="flex items-center gap-3 rounded-[1.75rem] bg-white/5 p-4 shadow-inner shadow-slate-950/10 backdrop-blur-sm">
              <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-slate-100 text-slate-950 shadow-sm">
                <span className="text-base font-semibold">{user?.username?.charAt(0) || 'A'}</span>
              </div>
              <div>
                <p className="text-sm font-semibold text-white">{user?.username}</p>
                <span className="inline-flex rounded-full bg-slate-800 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-slate-300">
                  {user?.role}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-slate-950/40 md:hidden"
          onClick={onClose}
          aria-label="Close sidebar"
        />
      )}
    </div>
  );
};

export default Sidebar;
