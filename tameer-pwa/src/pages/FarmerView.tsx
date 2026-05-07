import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLatestSnapshot } from '../hooks/useLatestSnapshot';
import { useAutomationEvents } from '../hooks/useAutomationEvents';
import KeyMetricsRow from '../components/farmer/KeyMetricsRow';
import ActuatorStatusGrid from '../components/farmer/ActuatorStatusGrid';
import CropHealthPanel from '../components/farmer/CropHealthPanel';
import AutomationAlert from '../components/farmer/AutomationAlert';
import RecommendationsPanel from '../components/shared/RecommendationsPanel';
import ErrorBanner from '../components/shared/ErrorBanner';

const ZONES = [1, 2];

export default function FarmerView() {
  const { t } = useTranslation();
  const [zoneId, setZoneId] = useState(1);
  const { data: snapshot, isLoading, isError } = useLatestSnapshot(zoneId);
  const { data: eventsData } = useAutomationEvents();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">{t('farmer.title')}</h1>
        <div className="flex gap-2">
          {ZONES.map(z => (
            <button
              key={z}
              onClick={() => setZoneId(z)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-colors ${
                zoneId === z
                  ? 'bg-primary text-white border-primary'
                  : 'bg-white text-primary border-primary hover:bg-primary/10'
              }`}
            >
              Zone {z}
            </button>
          ))}
        </div>
      </div>
      {isError && <ErrorBanner message={t('common.error')} />}
      <AutomationAlert events={eventsData?.events} />
      {isLoading && !snapshot ? (
        <p className="text-center text-gray-400 py-12">{t('common.loading')}</p>
      ) : (
        <>
          <KeyMetricsRow snapshot={snapshot} />
          <ActuatorStatusGrid events={eventsData?.events ?? []} />
          <RecommendationsPanel air={snapshot?.weather ?? undefined} />
          <CropHealthPanel snapshot={snapshot} />
        </>
      )}
    </div>
  );
}
