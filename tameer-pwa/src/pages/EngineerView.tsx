import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useSoilReadings } from '../hooks/useSoilReadings';
import { useAirReadings } from '../hooks/useAirReadings';
import { useAutomationEvents } from '../hooks/useAutomationEvents';
import { useHistory } from '../hooks/useHistory';
import SoilReadingsCard from '../components/engineer/SoilReadingsCard';
import AirReadingsCard from '../components/engineer/AirReadingsCard';
import MoistureChart from '../components/engineer/MoistureChart';
import AutomationEventLog from '../components/engineer/AutomationEventLog';
import ActuatorControls from '../components/engineer/ActuatorControls';
import RecommendationsPanel from '../components/shared/RecommendationsPanel';
import ErrorBanner from '../components/shared/ErrorBanner';

const ZONES = [1, 2];

export default function EngineerView() {
  const { t } = useTranslation();
  const [zoneId, setZoneId] = useState(1);
  const { data: soilData, isLoading, isError } = useSoilReadings(zoneId);
  const { data: airData } = useAirReadings(zoneId);
  const { data: eventsData } = useAutomationEvents();
  const { data: historyData } = useHistory(zoneId, 'soil_readings', 24);

  const soil = soilData?.data;
  const air = airData?.data;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-primary">{t('engineer.title')}</h1>
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
      {isLoading && !soil ? (
        <p className="text-center text-gray-400 py-12">{t('common.loading')}</p>
      ) : (
        <>
          <SoilReadingsCard soil={soil} />
          <AirReadingsCard air={air} />
          <RecommendationsPanel air={air} />
          <MoistureChart history={historyData?.data ?? []} />
          <ActuatorControls events={eventsData?.events ?? []} />
          <AutomationEventLog events={eventsData?.events ?? []} />
        </>
      )}
    </div>
  );
}
