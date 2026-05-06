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
import ErrorBanner from '../components/shared/ErrorBanner';

export default function EngineerView() {
  const { t } = useTranslation();
  const { data: soilData, isLoading, isError } = useSoilReadings();
  const { data: airData } = useAirReadings();
  const { data: eventsData } = useAutomationEvents();
  const { data: historyData } = useHistory(1, 'soil_readings', 24);

  const soil = soilData?.data?.[0];
  const air = airData?.data?.[0];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">{t('engineer.title')}</h1>
      {isError && <ErrorBanner message={t('common.error')} />}
      {isLoading && !soil ? (
        <p className="text-center text-gray-400 py-12">{t('common.loading')}</p>
      ) : (
        <>
          <SoilReadingsCard soil={soil} />
          <AirReadingsCard air={air} />
          <MoistureChart history={historyData?.data ?? []} />
          <ActuatorControls events={eventsData?.events ?? []} />
          <AutomationEventLog events={eventsData?.events ?? []} />
        </>
      )}
    </div>
  );
}
