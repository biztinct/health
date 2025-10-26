import { MobileHeader } from './MobileHeader';
import { BottomNavigation } from './BottomNavigation';
import { Avatar, AvatarFallback } from './ui/avatar';
import { Badge } from './ui/badge';
import { User } from 'lucide-react';

interface PatientDetailsScreenProps {
  onNavigate: (screen: any) => void;
}

export function PatientDetailsScreen({ onNavigate }: PatientDetailsScreenProps) {
  return (
    <div className="h-screen flex flex-col bg-slate-950">
      <MobileHeader
        title="Patient Details"
        onBack={() => onNavigate('orders')}
      />
      
      <div className="flex-1 overflow-y-auto pb-32">
        {/* Patient Card */}
        <div className="m-4 bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-6 border border-slate-700/50 shadow-xl">
          <div className="flex items-center gap-4">
            <Avatar className="w-16 h-16 bg-blue-500">
              <AvatarFallback>
                <User className="w-8 h-8" />
              </AvatarFallback>
            </Avatar>
            
            <div className="flex-1">
              <h2 className="text-xl mb-1">Client Beta2</h2>
              <p className="text-slate-400 text-sm mb-2">ID: 99 000012025</p>
              <Badge className="bg-emerald-500/20 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20">
                ACTIVE
              </Badge>
            </div>
          </div>
        </div>

        {/* Basic Information */}
        <div className="mx-4 mb-4 bg-white rounded-2xl p-6 shadow-lg">
          <div className="flex items-center gap-2 mb-6">
            <User className="w-5 h-5 text-blue-600" />
            <h3 className="text-slate-900 font-bold">Basic Information</h3>
          </div>
          
          <div className="space-y-5">
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                Full Name
              </label>
              <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                <span className="text-slate-400">-</span>
              </div>
            </div>
            
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                Date of Birth
              </label>
              <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                <span className="text-slate-400">-</span>
              </div>
            </div>
            
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                Age
              </label>
              <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                <span className="text-slate-400">-</span>
              </div>
            </div>
            
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide block mb-2">
                Gender
              </label>
              <div className="h-10 bg-slate-50 rounded-lg flex items-center px-3">
                <span className="text-slate-400">-</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <BottomNavigation activeTab="patients" onNavigate={onNavigate} />
    </div>
  );
}