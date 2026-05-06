import { useTranslation } from 'react-i18next';
import { useLatestSnapshot } from '../hooks/useLatestSnapshot';
import { useAutomationEvents } from '../hooks/useAutomationEvents';
import KeyMetricsRow from '../components/farmer/KeyMetricsRow';
import ActuatorStatusGrid from '../components/farmer/ActuatorStatusGrid';
import CropHealthPanel from '../components/farmer/CropHealthPanel';
import ManualUploadButton from '../components/farmer/ManualUploadButton';
import AutomationAlert from '../components/farmer/AutomationAlert';
import ErrorBanner from '../components/shared/ErrorBanner';

export default function FarmerView() {
  const { t } = useTranslation();
  const { data: snapshot, isLoading, isError } = useLatestSnapshot();
  const { data: eventsData } = useAutomationEvents();

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">{t('farmer.title')}</h1>
      {isError && <ErrorBanner message={t('common.error')} />}
      <AutomationAlert events={eventsData?.events} />
      {isLoading && !snapshot ? (
        <p className="text-center text-gray-400 py-12">{t('common.loading')}</p>
      ) : (
        <>
          <KeyMetricsRow snapshot={snapshot} />
          <ActuatorStatusGrid events={eventsData?.events ?? []} />
          <CropHealthPanel snapshot={snapshot} />
          <ManualUploadButton />
        </>
      )}
    </div>
  );
}
