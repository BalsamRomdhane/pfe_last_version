import React, { useContext } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { Users, Building, Activity, Settings, BarChart3 } from 'lucide-react';

const Sidebar = () => {
  const { user } = useContext(UserContext);
  const location = useLocation();

  const navigationItems = [
    {
      label: 'Dashboard',
      icon: <BarChart3 size={20} />,
      path: '/dashboard',
      roles: ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'],
    },
    {
      label: 'Users',
      icon: <Users size={20} />,
      path: '/users',
      roles: ['ADMIN'],
    },
    {
      label: 'Departments',
      icon: <Building size={20} />,
      path: '/departments',
      roles: ['ADMIN'],
    },
    {
      label: 'System',
      icon: <Settings size={20} />,
      path: '/system',
      roles: ['ADMIN'],
    },
  ];

  const filteredItems = navigationItems.filter(item =>
    item.roles.includes(user?.role)
  );

  return (
    <div className="w-64 bg-blue-900 text-white flex flex-col">
      {/* Logo Section */}
      <div className="p-6 border-b border-blue-800">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-white rounded flex items-center justify-center">
            <span className="text-blue-900 font-bold text-lg">C</span>
          </div>
          <div>
            <h2 className="text-sm font-semibold">Enterprise</h2>
            <p className="text-xs opacity-80">Platform</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {filteredItems.map((item) => {
            const isActive = location.pathname === item.path;
            return (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-blue-700 border-l-4 border-blue-400 text-white'
                      : 'text-blue-200 hover:bg-blue-800 hover:text-white'
                  }`}
                >
                  {item.icon}
                  <span className="font-medium">{item.label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* User Info Footer */}
      <div className="p-4 border-t border-blue-800">
        <div className="text-xs text-blue-300">
          <p className="font-medium">{user?.username}</p>
          <p className="opacity-75">{user?.role}</p>
        </div>
      </div>
    </div>
  );
};

export default Sidebar;
