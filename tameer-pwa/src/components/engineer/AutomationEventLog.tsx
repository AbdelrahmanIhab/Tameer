import { useTranslation } from 'react-i18next';
import type { AutomationEvent } from '../../types/api';

interface Props { events: AutomationEvent[] }

export default function AutomationEventLog({ events }: Props) {
  const { t } = useTranslation();
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.eventLog')} ({events.length})</h2>
      {events.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-4">No events in last 24h</p>
      ) : (
        <ul className="space-y-2 max-h-64 overflow-y-auto">
          {events.slice(0, 30).map((e, i) => {
            const isOn = e.action === 'on' || e.action === 'irrigate';
            return (
              <li key={i} className="border-b border-gray-100 pb-2 last:border-0">
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-sm capitalize">{e.actuator.replace(/_/g, ' ')}</span>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isOn ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {e.action.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5 truncate">{e.trigger_reason}</p>
                <p className="text-xs text-gray-400">{new Date(e.timestamp).toLocaleString()}</p>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
