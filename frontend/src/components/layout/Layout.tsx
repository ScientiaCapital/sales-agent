import { useState } from 'react';
import { Outlet, NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Search,
  Mail,
  MessageSquare,
  DollarSign,
  Upload,
  BookOpen,
  UserPlus,
  Bot,
  Menu,
  X,
} from 'lucide-react';

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  category: string;
}

const navigation: NavItem[] = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard, category: 'Overview' },
  { name: 'Leads', path: '/leads', icon: Users, category: 'Sales Operations' },
  { name: 'Contacts', path: '/contacts', icon: UserPlus, category: 'Sales Operations' },
  { name: 'Campaigns', path: '/campaigns', icon: Mail, category: 'Sales Operations' },
  { name: 'Research', path: '/research', icon: Search, category: 'Intelligence' },
  { name: 'Conversations', path: '/conversations', icon: MessageSquare, category: 'Intelligence' },
  { name: 'Knowledge Base', path: '/knowledge', icon: BookOpen, category: 'Intelligence' },
  { name: 'Agent Teams', path: '/agents', icon: Bot, category: 'Operations' },
  { name: 'Costs', path: '/costs', icon: DollarSign, category: 'Operations' },
  { name: 'CSV Import', path: '/csv-import', icon: Upload, category: 'Operations' },
];

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const groupedNavigation = navigation.reduce((acc, item) => {
    if (!acc[item.category]) {
      acc[item.category] = [];
    }
    acc[item.category].push(item);
    return acc;
  }, {} as Record<string, NavItem[]>);

  const NavContent = () => (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
        <div className="flex items-center space-x-2">
          <Bot className="h-8 w-8 text-indigo-600" />
          <span className="text-xl font-bold text-gray-900">Sales Agent</span>
        </div>
        <button
          onClick={() => setSidebarOpen(false)}
          className="lg:hidden p-1 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
        >
          <X className="h-6 w-6" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-8 overflow-y-auto">
        {Object.entries(groupedNavigation).map(([category, items]) => (
          <div key={category}>
            <h3 className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {category}
            </h3>
            <div className="mt-2 space-y-1">
              {items.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setSidebarOpen(false)}
                    className={`
                      group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors duration-150
                      ${
                        isActive
                          ? 'bg-indigo-50 text-indigo-600'
                          : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                      }
                    `}
                  >
                    <item.icon
                      className={`
                        mr-3 h-5 w-5 flex-shrink-0 transition-colors duration-150
                        ${isActive ? 'text-indigo-600' : 'text-gray-400 group-hover:text-gray-500'}
                      `}
                    />
                    {item.name}
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* User Profile */}
      <div className="flex-shrink-0 flex border-t border-gray-200 p-4">
        <div className="flex items-center">
          <div className="h-9 w-9 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
            U
          </div>
          <div className="ml-3">
            <p className="text-sm font-medium text-gray-700">User Account</p>
            <p className="text-xs text-gray-500">user@example.com</p>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 transition-opacity lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 w-64 bg-white transform transition-transform duration-300 ease-in-out lg:hidden
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <NavContent />
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex lg:flex-shrink-0">
        <div className="flex flex-col w-64 border-r border-gray-200 bg-white">
          <NavContent />
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Top bar */}
        <div className="relative z-10 flex-shrink-0 flex h-16 bg-white shadow">
          <button
            onClick={() => setSidebarOpen(true)}
            className="px-4 border-r border-gray-200 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 lg:hidden"
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex-1 px-4 flex items-center justify-between">
            <div className="flex-1 flex">
              <h1 className="text-xl font-semibold text-gray-900">
                {navigation.find((item) => item.path === location.pathname)?.name || 'Dashboard'}
              </h1>
            </div>
          </div>
        </div>

        {/* Page content */}
        <main className="flex-1 relative overflow-y-auto focus:outline-none">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
