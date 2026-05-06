import { useTranslation } from 'react-i18next';
import type { SoilReading } from '../../types/api';

interface Props { soil: SoilReading | undefined }

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-2 border-b border-gray-100 text-sm last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold text-gray-800">{value}</span>
    </div>
  );
}

export default function SoilReadingsCard({ soil }: Props) {
  const { t } = useTranslation();
  if (!soil) return null;
  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.soilReadings')}</h2>
      <Row label={t('engineer.moisture')} value={`${soil.moisture?.toFixed(1)} %`} />
      <Row label={t('engineer.soilTemp')} value={`${soil.soil_temp?.toFixed(1)} °C`} />
      <Row label={t('engineer.ec')} value={`${soil.ec?.toFixed(2)} mS/cm`} />
      <Row label={t('engineer.ph')} value={`${soil.ph?.toFixed(1)}`} />
      <Row label={t('engineer.nitrogen')} value={`${soil.nitrogen?.toFixed(0)} mg/kg`} />
      <Row label={t('engineer.phosphorus')} value={`${soil.phosphorus?.toFixed(0)} mg/kg`} />
      <Row label={t('engineer.potassium')} value={`${soil.potassium?.toFixed(0)} mg/kg`} />
      <Row label={t('engineer.dryness')} value={soil.dryness_level ?? '-'} />
    </div>
  );
}
