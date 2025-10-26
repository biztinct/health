import { useState } from 'react';
import { PatientDetailsScreen } from './components/PatientDetailsScreen';
import { FieldOrdersScreen } from './components/FieldOrdersScreen';
import { OrderDetailsScreen } from './components/OrderDetailsScreen';
import { DashboardScreen } from './components/DashboardScreen';

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<'dashboard' | 'patients' | 'orders' | 'order-details'>('dashboard');

  return (
    <div className="size-full bg-slate-950 text-white overflow-hidden">
      {currentScreen === 'dashboard' && (
        <DashboardScreen onNavigate={setCurrentScreen} />
      )}
      {currentScreen === 'patients' && (
        <PatientDetailsScreen onNavigate={setCurrentScreen} />
      )}
      {currentScreen === 'orders' && (
        <FieldOrdersScreen onNavigate={setCurrentScreen} />
      )}
      {currentScreen === 'order-details' && (
        <OrderDetailsScreen onNavigate={setCurrentScreen} />
      )}
    </div>
  );
}