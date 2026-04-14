import React, { useContext } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import { Users, Building, Activity, CheckCircle } from 'lucide-react';

const Dashboard = () => {
  const { user, userProfile } = useContext(UserContext);

  const displayDepartment = userProfile?.department || user?.department || (user?.role === 'ADMIN' ? 'Global' : 'N/A');

  const stats = [
    {
      title: 'Total Users',
      value: '---',
      subtitle: 'Go to Users to view',
      icon: <Users size={24} />,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    {
      title: 'Departments',
      value: '4',
      subtitle: 'DIGITAL, AERONAUTIQUE, AUTOMOBILE, QUALITE',
      icon: <Building size={24} />,
      color: 'text-orange-600',
      bgColor: 'bg-orange-100',
    },
    {
      title: 'Active Sessions',
      value: '1',
      subtitle: 'Current session',
      icon: <Activity size={24} />,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    {
      title: 'System Status',
      value: 'Online',
      subtitle: 'All systems operational',
      icon: <CheckCircle size={24} />,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
  ];

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard Overview</h1>
          <p className="text-gray-600 mt-1">Welcome back, {user?.username}</p>
        </div>

        {/* User Info Card */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">User Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Username</p>
              <p className="text-lg font-medium text-gray-900">{user?.username}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500">Role</p>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                {user?.role}
              </span>
            </div>
            <div className="md:col-span-2">
              <p className="text-sm text-gray-500">Department</p>
              <p className="text-lg font-medium text-gray-900">{displayDepartment}</p>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        {user?.role === 'ADMIN' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {stats.map((stat, index) => (
              <div key={index} className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow duration-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-600">{stat.title}</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{stat.value}</p>
                    <p className="text-xs text-gray-500 mt-1">{stat.subtitle}</p>
                  </div>
                  <div className={`p-3 rounded-lg ${stat.bgColor}`}>
                    <div className={stat.color}>
                      {stat.icon}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </Layout>
  );
};

export default Dashboard;
