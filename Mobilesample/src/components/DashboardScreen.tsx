import { MobileHeader } from './MobileHeader';
import { BottomNavigation } from './BottomNavigation';
import { Users, FileText, UsersRound, RefreshCw, Bug } from 'lucide-react';
import { Button } from './ui/button';

interface DashboardScreenProps {
  onNavigate: (screen: any) => void;
}

export function DashboardScreen({ onNavigate }: DashboardScreenProps) {
  const mainCards = [
    {
      id: 'patients',
      title: 'Patients',
      subtitle: 'Manage patient records',
      icon: Users,
      gradient: 'from-blue-600 to-blue-700',
      onClick: () => onNavigate('patients'),
    },
    {
      id: 'orders',
      title: 'Field Orders',
      subtitle: 'View service orders',
      icon: FileText,
      gradient: 'from-red-600 to-red-700',
      onClick: () => onNavigate('orders'),
    },
    {
      id: 'teams',
      title: 'Teams',
      subtitle: 'Team management',
      icon: UsersRound,
      gradient: 'from-green-600 to-green-700',
      onClick: () => {},
    },
  ];

  const actionButtons = [
    {
      id: 'sync',
      label: 'Sync Data',
      icon: RefreshCw,
      color: 'bg-blue-600 hover:bg-blue-700',
    },
    {
      id: 'force-sync',
      label: 'Force Full Sync',
      icon: RefreshCw,
      color: 'bg-white hover:bg-slate-50',
      textColor: 'text-slate-900',
    },
    {
      id: 'debug',
      label: 'Debug Info',
      icon: Bug,
      color: 'bg-white hover:bg-slate-50',
      textColor: 'text-slate-900',
    },
  ];

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <MobileHeader
        title="Dashboard"
        rightAction={
          <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
        }
      />
      
      <div className="flex-1 overflow-y-auto pb-32">
        {/* Welcome Message */}
        <div className="px-6 py-6">
          <p className="text-slate-600">Welcome back, Mitchell Admin</p>
        </div>

        {/* Main Navigation Cards */}
        <div className="px-6 space-y-4 mb-6">
          {mainCards.map((card) => {
            const Icon = card.icon;
            return (
              <button
                key={card.id}
                onClick={card.onClick}
                className={`w-full bg-gradient-to-r ${card.gradient} rounded-2xl p-6 shadow-lg transition-all hover:scale-[1.02] active:scale-95 text-left`}
              >
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 bg-white/20 rounded-xl flex items-center justify-center flex-shrink-0">
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h3 className="text-white mb-1">{card.title}</h3>
                    <p className="text-white/80 text-sm">{card.subtitle}</p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="px-6 grid grid-cols-3 gap-3">
          {actionButtons.map((button) => {
            const Icon = button.icon;
            return (
              <Button
                key={button.id}
                onClick={() => {}}
                className={`${button.color} ${button.textColor || 'text-white'} flex flex-col h-auto py-4 px-3 shadow-md rounded-xl hover:shadow-lg transition-all`}
              >
                <Icon className="w-5 h-5 mb-2" />
                <span className="text-xs text-center leading-tight whitespace-normal">
                  {button.label}
                </span>
              </Button>
            );
          })}
        </div>
      </div>
      
      <BottomNavigation activeTab="dashboard" onNavigate={onNavigate} />
    </div>
  );
}
