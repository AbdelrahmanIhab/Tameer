import { useTranslation } from 'react-i18next';
import type { AutomationEvent, ActuatorName } from '../../types/api';
import { useManualOverride } from '../../hooks/useManualOverride';

const ACTUATORS: ActuatorName[] = [
  'irrigation_valve', 'fertilizer_pump', 'fan', 'heater', 'grow_light', 'shade', 'spray_nozzle',
];

function deriveStates(events: AutomationEvent[]): Record<string, boolean> {
  const state: Record<string, boolean> = {};
  const sorted = [...events].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  for (const e of sorted) {
    if (!(e.actuator in state)) state[e.actuator] = e.action === 'on' || e.action === 'irrigate';
  }
  return state;
}

interface Props { events: AutomationEvent[] }

export default function ActuatorControls({ events }: Props) {
  const { t } = useTranslation();
  const { mutate, isPending, variables } = useManualOverride();
  const states = deriveStates(events);

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.manualOverride')}</h2>
      <div className="space-y-1">
        {ACTUATORS.map(actuator => {
          const isOn = states[actuator] ?? false;
          const loading = isPending && variables?.actuator === actuator;
          return (
            <div key={actuator} className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0">
              <span className="text-sm text-gray-700">{t(`engineer.actuators.${actuator}`)}</span>
              <button
                disabled={isPending}
                onClick={() => mutate({ target_node: 1, actuator, action: isOn ? 'off' : 'on' })}
                className={`w-14 h-7 rounded-full transition-colors text-xs font-bold text-white disabled:opacity-50 ${isOn ? 'bg-primary' : 'bg-gray-300'}`}
              >
                {loading ? '…' : isOn ? t('engineer.on') : t('engineer.off')}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
