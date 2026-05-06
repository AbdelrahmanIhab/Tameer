import { useTranslation } from 'react-i18next';
import type { LatestSnapshot } from '../../types/api';

interface Props { snapshot: LatestSnapshot | undefined }

function Box({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-3 flex-1 text-center">
      <div className={`text-xl font-bold ${color ?? 'text-primary'}`}>{value}</div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  );
}

export default function KeyMetricsRow({ snapshot }: Props) {
  const { t } = useTranslation();
  if (!snapshot) return null;

  const m = snapshot.soil?.moisture;
  const moistureColor = m == null ? 'text-gray-400' : m < 40 ? 'text-red-600' : m > 85 ? 'text-blue-600' : 'text-primary';

  return (
    <div className="flex gap-3">
      <Box label={t('farmer.moisture')} value={m != null ? `${m.toFixed(0)}%` : '--'} color={moistureColor} />
      <Box label={t('farmer.airTemp')} value={snapshot.weather?.air_temp != null ? `${snapshot.weather.air_temp.toFixed(1)}°C` : '--'} />
      <Box label={t('farmer.rain')} value={snapshot.weather?.rain === 1 ? '🌧' : '☀️'} />
      <Box label={t('farmer.lastAction')} value={snapshot.soil?.dryness_level ?? '--'} />
    </div>
  );
}
