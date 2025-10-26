import { MobileHeader } from './MobileHeader';
import { BottomNavigation } from './BottomNavigation';
import { Badge } from './ui/badge';
import { Button } from './ui/button';
import { FileText, ChevronRight, History } from 'lucide-react';

interface FieldOrdersScreenProps {
  onNavigate: (screen: any) => void;
}

const orders = [
  {
    id: '1',
    title: 'Home Visit',
    subtitle: 'Scheduled: Today, 2:00 PM',
    status: 'completed',
    statusLabel: 'COMPLETED',
  },
  {
    id: '2',
    title: 'Clinic Visit',
    subtitle: 'Scheduled: Today, 3:30 PM',
    status: 'in-progress',
    statusLabel: 'IN PROGRESS',
  },
  {
    id: '3',
    title: 'Home Visit',
    subtitle: 'Scheduled: Tomorrow, 10:00 AM',
    status: 'assigned',
    statusLabel: 'ASSIGNED',
  },
  {
    id: '4',
    title: 'Consultation',
    subtitle: 'Scheduled: Tomorrow, 2:00 PM',
    status: 'completed',
    statusLabel: 'COMPLETED',
  },
  {
    id: '5',
    title: 'Home Visit',
    subtitle: 'Scheduled: Oct 28, 9:00 AM',
    status: 'completed',
    statusLabel: 'COMPLETED',
  },
];

export function FieldOrdersScreen({ onNavigate }: FieldOrdersScreenProps) {
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      case 'in-progress':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      case 'assigned':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
    }
  };

  return (
    <div className="h-screen flex flex-col bg-slate-950">
      <MobileHeader title="Field Orders" />
      
      <div className="flex-1 overflow-y-auto pb-32">
        {/* Past Bookings Button */}
        <div className="m-4 bg-white rounded-2xl p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-slate-900 mb-1">Upcoming</h3>
              <p className="text-slate-500 text-sm">5 field orders</p>
            </div>
            <Button
              onClick={() => {}}
              className="bg-slate-900 hover:bg-slate-800 text-white"
            >
              <History className="w-4 h-4 mr-2" />
              View Past Bookings
            </Button>
          </div>
        </div>

        {/* Orders List */}
        <div className="px-4 space-y-3">
          {orders.map((order) => (
            <button
              key={order.id}
              onClick={() => onNavigate('order-details')}
              className="w-full bg-slate-900 hover:bg-slate-800 rounded-2xl p-4 border border-slate-800 transition-all hover:border-slate-700 shadow-lg group"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-gradient-to-br from-rose-500 to-rose-600 rounded-xl flex items-center justify-center flex-shrink-0 shadow-lg">
                  <FileText className="w-6 h-6" />
                </div>
                
                <div className="flex-1 text-left min-w-0">
                  <h3 className="text-white mb-1 truncate">{order.title}</h3>
                  <p className="text-slate-400 text-sm truncate">{order.subtitle}</p>
                </div>
                
                <div className="flex items-center gap-3 flex-shrink-0">
                  <Badge className={`${getStatusColor(order.status)} hover:${getStatusColor(order.status)} text-xs px-3`}>
                    {order.statusLabel}
                  </Badge>
                  <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-slate-400 transition-colors" />
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
      
      <BottomNavigation activeTab="orders" onNavigate={onNavigate} />
    </div>
  );
}
