import { LayoutDashboard, Users, FileText, UsersRound, UserCircle } from 'lucide-react';

interface BottomNavigationProps {
  activeTab: 'dashboard' | 'patients' | 'orders' | 'teams' | 'profile';
  onNavigate: (screen: any) => void;
}

export function BottomNavigation({ activeTab, onNavigate }: BottomNavigationProps) {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, screen: 'dashboard' },
    { id: 'patients', label: 'Patients', icon: Users, screen: 'patients' },
    { id: 'orders', label: 'Orders', icon: FileText, screen: 'orders' },
    { id: 'teams', label: 'Teams', icon: UsersRound, screen: null },
    { id: 'profile', label: 'Profile', icon: UserCircle, screen: null },
  ];

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 pb-safe">
      <div className="grid grid-cols-5 gap-1 px-2 py-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => tab.screen && onNavigate(tab.screen)}
              className="flex flex-col items-center gap-1 py-2 px-1 rounded-lg transition-colors hover:bg-slate-800"
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-blue-400' : 'text-slate-400'}`} />
              <span className={`text-xs ${isActive ? 'text-blue-400' : 'text-slate-400'}`}>
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
      <div className="h-6 bg-slate-900" />
    </div>
  );
}