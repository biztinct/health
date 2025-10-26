import { useState, useEffect } from 'react';
import { MobileHeader } from './MobileHeader';
import { BottomNavigation } from './BottomNavigation';
import { Badge } from './ui/badge';
import { MapPin, Lock, CheckCircle, User, Briefcase, Calendar, Clock, AlertCircle } from 'lucide-react';

interface OrderDetailsScreenProps {
  onNavigate: (screen: any) => void;
}

export function OrderDetailsScreen({ onNavigate }: OrderDetailsScreenProps) {
  // Timer state - starting from 184 hours, 39 minutes, 16 seconds
  const [elapsedSeconds, setElapsedSeconds] = useState(664756); // 184:39:16 in seconds

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsedSeconds(prev => prev + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const formatTime = (totalSeconds: number) => {
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

  const actionButtons = [
    {
      id: 'location',
      label: 'LOCATION MAP',
      icon: MapPin,
      color: 'from-[#43A047] to-[#388E3C]',
    },
    {
      id: 'notes',
      label: 'CLINICAL NOTES',
      icon: Lock,
      color: 'from-[#1565C0] to-[#0D47A1]',
    },
    {
      id: 'complete',
      label: 'COMPLETE SERVICE',
      icon: CheckCircle,
      color: 'from-[#FB8C00] to-[#EF6C00]',
      fullWidth: true,
    },
  ];

  return (
    <div className="h-screen flex flex-col bg-slate-50">
      <MobileHeader
        title="Order Details"
        onBack={() => onNavigate('orders')}
        rightAction={
          <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
        }
      />
      
      <div className="flex-1 overflow-y-auto pb-32 bg-white">
        {/* Client Header */}
        <div className="px-6 pt-4 pb-2 bg-white">
          <h2 className="text-slate-900 mb-2 font-bold text-[32px]">Client Beta3</h2>
          <div className="flex items-center gap-2">
            <span className="text-blue-600 text-sm">📋 FSO-1102</span>
            <span className="text-slate-300">•</span>
            <Badge className="bg-purple-100 text-purple-600 border-0 hover:bg-purple-100">
              IN PROGRESS
            </Badge>
          </div>
        </div>

        {/* Timer Card */}
        <div className="px-6 py-4">
          <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-2xl p-6 shadow-xl border border-slate-700/50 overflow-hidden relative">
            {/* Subtle animated background effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 via-purple-500/5 to-pink-500/5"></div>
            
            <div className="relative">
              {/* Elapsed Time Label - Minimal & Clean */}
              <div className="flex items-center justify-between mb-4">
                <span className="text-slate-400 text-xs tracking-[0.2em] uppercase">
                  Elapsed Time
                </span>
                <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  <span className="text-emerald-400 text-xs">Live</span>
                </div>
              </div>
              
              {/* Timer Display - Large & Bold */}
              <div className="mb-4">
                <span className="text-6xl text-white tracking-tighter block tabular-nums">
                  {formatTime(elapsedSeconds)}
                </span>
              </div>
              
              {/* Started Time - Subtle */}
              <div className="flex items-center gap-2 pt-3 border-t border-slate-700/50">
                <div className="w-1.5 h-1.5 rounded-full bg-slate-500"></div>
                <p className="text-slate-400 text-xs">
                  Started 19/10/2025 at 05:01:14
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Action Buttons Grid */}
        <div className="px-6 grid grid-cols-2 gap-3 mb-4">
          {actionButtons.slice(0, 2).map((button) => {
            const Icon = button.icon;
            return (
              <button
                key={button.id}
                className={`bg-gradient-to-br ${button.color} hover:opacity-90 rounded-2xl p-6 shadow-lg transition-all hover:scale-[1.02] active:scale-95 text-left`}
              >
                <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-3">
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <span className="block text-white text-sm">{button.label}</span>
              </button>
            );
          })}
        </div>
        
        <div className="px-6 mb-4">
          {actionButtons.slice(2).map((button) => {
            const Icon = button.icon;
            return (
              <button
                key={button.id}
                className={`w-full bg-gradient-to-br ${button.color} hover:opacity-90 rounded-2xl p-6 shadow-lg transition-all hover:scale-[1.01] active:scale-95 text-left`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                    <Icon className="w-5 h-5 text-white" />
                  </div>
                  <span className="text-white text-sm">{button.label}</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Order Details Sections */}
        <div className="px-6 space-y-4 pb-6">
          {/* Patient Information */}
          <div className="bg-white rounded-2xl p-6 shadow-lg">
            <div className="flex items-center gap-2 mb-6">
              <User className="w-5 h-5 text-blue-600" />
              <h3 className="text-slate-900 font-bold">Patient Information</h3>
            </div>
            
            <div className="space-y-5">
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                  Name
                </label>
                <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                  <span className="text-slate-900">Client Beta3</span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                    Age
                  </label>
                  <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                    <span className="text-slate-900">15</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                    Gender
                  </label>
                  <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                    <span className="text-slate-900">Male</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Service Information */}
          <div className="bg-white rounded-2xl p-6 shadow-lg">
            <div className="flex items-center gap-2 mb-6">
              <Briefcase className="w-5 h-5 text-purple-600" />
              <h3 className="text-slate-900 font-bold">Service Information</h3>
            </div>
            
            <div className="space-y-5">
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                  Scheduled Time
                </label>
                <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                  <span className="text-slate-900">28/10/2025, 05:00:00</span>
                </div>
              </div>
              
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                  Estimated Duration
                </label>
                <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                  <span className="text-slate-900">1 hours</span>
                </div>
              </div>
              
              <div>
                <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                  Priority
                </label>
                <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                  <Badge className="bg-red-100 text-red-700 border-0 hover:bg-red-100">
                    HIGH
                  </Badge>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <BottomNavigation activeTab="orders" onNavigate={onNavigate} />
    </div>
  );
}