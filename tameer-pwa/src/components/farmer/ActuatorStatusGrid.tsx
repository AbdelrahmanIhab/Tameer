import { useTranslation } from 'react-i18next';
import type { AutomationEvent } from '../../types/api';

function deriveIrrigationState(events: AutomationEvent[]): boolean {
  const sorted = [...events].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  const latest = sorted.find(e => e.actuator === 'irrigation_valve');
  return latest ? latest.action === 'on' || latest.action === 'irrigate' : false;
}

interface Props { events: AutomationEvent[] }

export default function ActuatorStatusGrid({ events }: Props) {
  const { t } = useTranslation();
  const isOn = deriveIrrigationState(events);

  return (
    <div className={`bg-white rounded-xl p-3 flex items-center gap-3 border-2 transition-colors ${isOn ? 'border-primary' : 'border-gray-200'}`}>
      <span className="text-3xl">💧</span>
      <div>
        <div className="text-sm font-semibold text-gray-700">{t('engineer.actuators.irrigation_valve')}</div>
        <div className={`text-xs font-bold ${isOn ? 'text-primary' : 'text-gray-400'}`}>
          {isOn ? t('engineer.on') : t('engineer.off')}
        </div>
      </div>
    </div>
  );
}
