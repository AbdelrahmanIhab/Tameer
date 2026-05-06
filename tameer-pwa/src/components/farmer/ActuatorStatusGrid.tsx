import { useTranslation } from 'react-i18next';
import type { AutomationEvent, ActuatorName } from '../../types/api';

const ICONS: Record<ActuatorName, string> = {
  irrigation_valve: '💧', fertilizer_pump: '🧪', fan: '🌀',
  heater: '🔥', grow_light: '💡', shade: '☂️', spray_nozzle: '🚿',
};

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

export default function ActuatorStatusGrid({ events }: Props) {
  const { t } = useTranslation();
  const states = deriveStates(events);

  return (
    <div className="grid grid-cols-4 gap-2">
      {ACTUATORS.map(actuator => {
        const isOn = states[actuator] ?? false;
        return (
          <div
            key={actuator}
            className={`bg-white rounded-xl p-3 flex flex-col items-center gap-1 border-2 transition-colors ${isOn ? 'border-primary' : 'border-gray-200'}`}
          >
            <span className="text-2xl">{ICONS[actuator]}</span>
            <span className={`text-[10px] font-semibold text-center leading-tight ${isOn ? 'text-primary' : 'text-gray-400'}`}>
              {t(`engineer.actuators.${actuator}`)}
            </span>
            <span className={`text-[10px] font-bold ${isOn ? 'text-primary' : 'text-gray-300'}`}>
              {isOn ? t('engineer.on') : t('engineer.off')}
            </span>
          </div>
        );
      })}
    </div>
  );
}
