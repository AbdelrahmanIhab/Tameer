import { useTranslation } from 'react-i18next';
import type { AutomationEvent } from '../../types/api';
import { useManualOverride } from '../../hooks/useManualOverride';

function deriveIrrigationState(events: AutomationEvent[]): boolean {
  const sorted = [...events].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  const latest = sorted.find(e => e.actuator === 'irrigation_valve');
  return latest ? latest.action === 'on' || latest.action === 'irrigate' : false;
}

interface Props { events: AutomationEvent[] }

export default function ActuatorControls({ events }: Props) {
  const { t } = useTranslation();
  const { mutate, isPending } = useManualOverride();
  const isOn = deriveIrrigationState(events);

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.irrigationControl')}</h2>
      <div className="flex justify-between items-center py-2">
        <span className="text-sm text-gray-700">{t('engineer.actuators.irrigation_valve')}</span>
        <button
          disabled={isPending}
          onClick={() => mutate({ target_node: 1, actuator: 'irrigation_valve', action: isOn ? 'off' : 'on' })}
          className={`w-14 h-7 rounded-full transition-colors text-xs font-bold text-white disabled:opacity-50 ${isOn ? 'bg-primary' : 'bg-gray-300'}`}
        >
          {isPending ? '…' : isOn ? t('engineer.on') : t('engineer.off')}
        </button>
      </div>
    </div>
  );
}
