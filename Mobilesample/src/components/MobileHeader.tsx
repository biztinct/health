import { ArrowLeft } from 'lucide-react';

interface MobileHeaderProps {
  title: string;
  onBack?: () => void;
  rightAction?: React.ReactNode;
}

export function MobileHeader({ title, onBack, rightAction }: MobileHeaderProps) {
  return (
    <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur-sm border-b border-slate-800">
      <div className="px-4 py-4 flex items-center justify-between">
        {onBack ? (
          <button
            onClick={onBack}
            className="p-2 -ml-2 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-blue-400" />
          </button>
        ) : (
          <div className="w-9" />
        )}
        
        <h1 className="flex-1 text-center">{title}</h1>
        
        <div className="w-9">
          {rightAction}
        </div>
      </div>
    </div>
  );
}
