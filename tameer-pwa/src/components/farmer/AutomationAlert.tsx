import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { AutomationEvent } from '../../types/api';

interface Props { events: AutomationEvent[] | undefined }

export default function AutomationAlert({ events }: Props) {
  const { t } = useTranslation();
  const [msg, setMsg] = useState('');
  const prevCount = useRef<number | null>(null);

  useEffect(() => {
    if (!events) return;
    if (prevCount.current !== null && events.length > prevCount.current) {
      const latest = events[0];
      setMsg(`${latest.actuator.replace(/_/g, ' ')} — ${latest.trigger_reason}`);
      const timer = setTimeout(() => setMsg(''), 5000);
      return () => clearTimeout(timer);
    }
    prevCount.current = events.length;
  }, [events]);

  if (!msg) return null;

  return (
    <div className="bg-orange-50 border border-orange-200 text-orange-800 rounded-xl px-4 py-3 text-sm flex justify-between items-start">
      <span>⚡ {t('farmer.automationFired')}: {msg}</span>
      <button onClick={() => setMsg('')} className="ml-2 text-orange-400 hover:text-orange-600">✕</button>
    </div>
  );
}
