import React, { useContext, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import {
  BarChart3,
  Users,
  Building,
  Activity,
  Settings,
  ShieldCheck,
  ChevronLeft,
  X,
} from 'lucide-react';

const Sidebar = ({ mobileOpen, onClose }) => {
  const { user } = useContext(UserContext);
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

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
          label: 'API Testing',
          icon: <Activity size={18} />,
          path: '/api-testing',
          roles: ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'],
        },
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

  const sidebarWidth = collapsed ? 'w-20' : 'w-72';
  const itemLabel = collapsed ? 'hidden' : 'block';

  return (
    <div>
      <div
        className={`fixed inset-y-0 left-0 z-50 transform bg-gradient-to-b from-blue-700 to-blue-900 text-white shadow-2xl transition-transform duration-300 md:static md:translate-x-0 ${sidebarWidth} ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className="flex h-full flex-col justify-between overflow-hidden">
          <div>
            <div className="flex items-center justify-between gap-3 border-b border-blue-800 px-6 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-blue-900 shadow-sm">
                  <ShieldCheck size={20} />
                </div>
                {!collapsed && (
                  <div>
                    <p className="text-sm font-semibold tracking-wide">Enterprise</p>
                    <p className="text-xs text-blue-200">Admin Suite</p>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={() => (mobileOpen ? onClose() : setCollapsed(!collapsed))}
                className="rounded-full bg-white/10 p-2 text-blue-100 transition hover:bg-white/20 md:hidden"
              >
                <X size={18} />
              </button>
            </div>

            <div className="px-4 py-5">
              {filteredSections.map((section) =>
                section.items.length > 0 ? (
                  <div key={section.title} className="mb-6">
                    {!collapsed && (
                      <div className="px-3 pb-2 text-xs font-semibold uppercase tracking-[0.18em] text-blue-200/80">
                        {section.title}
                      </div>
                    )}
                    <div className="space-y-2">
                      {section.items.map((item) => {
                        const active = location.pathname === item.path;
                        return (
                          <Link
                            key={item.path}
                            to={item.path}
                            onClick={onClose}
                            className={`flex items-center gap-3 rounded-2xl px-4 py-3 transition-all duration-200 ${
                              active
                                ? 'bg-white/10 text-white shadow-lg ring-1 ring-white/20'
                                : 'text-blue-100 hover:bg-white/10 hover:text-white'
                            }`}
                          >
                            <div className={`flex h-10 w-10 items-center justify-center rounded-2xl ${active ? 'bg-white/15' : 'bg-white/5'}`}>
                              {item.icon}
                            </div>
                            <span className={`${itemLabel} font-medium`}>{item.label}</span>
                          </Link>
                        );
                      })}
                    </div>
                  </div>
                ) : null
              )}
            </div>
          </div>

          <div className="border-t border-blue-800 p-6">
            <div className="flex items-center gap-3 rounded-3xl bg-white/10 p-4 backdrop-blur">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white text-blue-900 shadow-sm">
                <span className="font-semibold">{user?.username?.charAt(0) || 'A'}</span>
              </div>
              {!collapsed && (
                <div>
                  <p className="text-sm font-semibold">{user?.username}</p>
                  <p className="text-xs text-blue-200">{user?.role}</p>
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => setCollapsed(!collapsed)}
              className="mt-4 flex w-full items-center justify-center rounded-2xl border border-white/10 bg-white/10 px-3 py-3 text-sm font-medium text-white transition hover:bg-white/15"
            >
              <ChevronLeft size={18} className={`${collapsed ? 'rotate-180' : ''} transition-transform duration-200`} />
              <span className={`${itemLabel} ml-2`}>{collapsed ? 'Expand' : 'Collapse'}</span>
            </button>
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
