import React, { useContext } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import { Server, Database, Shield, Activity } from 'lucide-react';

const System = () => {
  const { user } = useContext(UserContext);

  if (user?.role !== 'ADMIN') {
    return (
      <Layout>
        <div className="text-center py-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h2>
          <p className="text-gray-600">You don't have permission to view this page.</p>
        </div>
      </Layout>
    );
  }

  const systemInfo = [
    {
      title: 'Backend',
      icon: <Server size={24} />,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
      details: [
        { label: 'Framework', value: 'Django REST Framework' },
        { label: 'Version', value: '5.2' },
        { label: 'Python', value: '3.11' },
        { label: 'Status', value: 'Running' },
      ],
    },
    {
      title: 'Database',
      icon: <Database size={24} />,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
      details: [
        { label: 'Type', value: 'SQLite' },
        { label: 'Status', value: 'Connected' },
        { label: 'Tables', value: '8' },
        { label: 'Size', value: '~2MB' },
      ],
    },
    {
      title: 'Authentication',
      icon: <Shield size={24} />,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
      details: [
        { label: 'Provider', value: 'Keycloak + Django' },
        { label: 'JWT', value: 'Enabled' },
        { label: 'Sessions', value: '1 Active' },
        { label: 'Security', value: 'High' },
      ],
    },
    {
      title: 'Frontend',
      icon: <Activity size={24} />,
      color: 'text-orange-600',
      bgColor: 'bg-orange-100',
      details: [
        { label: 'Framework', value: 'React' },
        { label: 'UI Library', value: 'TailwindCSS' },
        { label: 'State', value: 'Context API' },
        { label: 'Build', value: 'Development' },
      ],
    },
  ];

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">System Information</h1>
          <p className="text-gray-600 mt-1">System status and configuration details</p>
        </div>

        {/* System Status Overview */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">System Status</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <div className="w-6 h-6 bg-green-500 rounded-full"></div>
              </div>
              <p className="text-sm font-medium text-gray-900">Backend</p>
              <p className="text-xs text-green-600">Online</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <div className="w-6 h-6 bg-green-500 rounded-full"></div>
              </div>
              <p className="text-sm font-medium text-gray-900">Database</p>
              <p className="text-xs text-green-600">Connected</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <div className="w-6 h-6 bg-green-500 rounded-full"></div>
              </div>
              <p className="text-sm font-medium text-gray-900">Auth Service</p>
              <p className="text-xs text-green-600">Active</p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <div className="w-6 h-6 bg-green-500 rounded-full"></div>
              </div>
              <p className="text-sm font-medium text-gray-900">Frontend</p>
              <p className="text-xs text-green-600">Running</p>
            </div>
          </div>
        </div>

        {/* Detailed System Information */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {systemInfo.map((system, index) => (
            <div key={index} className="bg-white rounded-xl shadow-md p-6">
              <div className="flex items-center space-x-4 mb-4">
                <div className={`p-3 rounded-lg ${system.bgColor}`}>
                  <div className={system.color}>
                    {system.icon}
                  </div>
                </div>
                <h3 className="text-lg font-semibold text-gray-900">{system.title}</h3>
              </div>

              <div className="space-y-3">
                {system.details.map((detail, idx) => (
                  <div key={idx} className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">{detail.label}:</span>
                    <span className="text-sm font-medium text-gray-900">{detail.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Environment Variables */}
        <div className="bg-white rounded-xl shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Environment Configuration</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <h4 className="font-medium text-gray-900">Backend</h4>
              <div className="text-sm text-gray-600 space-y-1">
                <p>DJANGO_SETTINGS_MODULE: enterprise_platform.settings</p>
                <p>DEBUG: True</p>
                <p>DATABASE_URL: SQLite</p>
              </div>
            </div>
            <div className="space-y-2">
              <h4 className="font-medium text-gray-900">Frontend</h4>
              <div className="text-sm text-gray-600 space-y-1">
                <p>REACT_APP_API_URL: http://localhost:8000/api</p>
                <p>NODE_ENV: development</p>
                <p>PORT: 3000</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default System;