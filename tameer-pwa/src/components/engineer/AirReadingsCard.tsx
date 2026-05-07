import { useTranslation } from 'react-i18next';
import type { AirReading } from '../../types/api';

interface Props { air: AirReading | undefined }

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 text-sm last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-800">{value}</span>
    </div>
  );
}

export default function AirReadingsCard({ air }: Props) {
  const { t } = useTranslation();
  if (!air) return null;
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.airReadings')}</h2>
      <Row label={t('engineer.airTemp')} value={`${air.air_temp?.toFixed(1)} °C`} />
      <Row label={t('engineer.humidity')} value={`${air.air_humidity?.toFixed(1)} %`} />
      <Row label={t('engineer.light')} value={`${air.light?.toFixed(0)} %`} />
      <Row label={t('engineer.airQuality')} value={`${air.air_quality?.toFixed(0)} %`} />
    </div>
  );
}
