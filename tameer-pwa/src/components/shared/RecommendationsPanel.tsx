import { useTranslation } from 'react-i18next';
import type { AirReading } from '../../types/api';

const THRESHOLDS = {
  air_temp_hot:  35,
  air_temp_cold: 10,
  light_low:     20,
};

interface Recommendation {
  icon: string;
  messageEn: string;
  messageAr: string;
  reading: string;
}

function buildRecommendations(air: AirReading, t: (k: string) => string): Recommendation[] {
  const recs: Recommendation[] = [];
  const lang = t('common.langToggle') === 'English' ? 'ar' : 'en';

  if (air.air_temp > THRESHOLDS.air_temp_hot) {
    recs.push({
      icon: '🌀',
      messageEn: `High temperature (${air.air_temp.toFixed(1)}°C). Consider cooling the area.`,
      messageAr: `درجة حرارة مرتفعة (${air.air_temp.toFixed(1)}°C). يُنصح بتبريد المنطقة.`,
      reading: `${air.air_temp.toFixed(1)}°C`,
    });
  }
  if (air.air_temp < THRESHOLDS.air_temp_cold) {
    recs.push({
      icon: '🔥',
      messageEn: `Low temperature (${air.air_temp.toFixed(1)}°C). Consider heating the area.`,
      messageAr: `درجة حرارة منخفضة (${air.air_temp.toFixed(1)}°C). يُنصح بتدفئة المنطقة.`,
      reading: `${air.air_temp.toFixed(1)}°C`,
    });
  }
  if (air.light < THRESHOLDS.light_low) {
    recs.push({
      icon: '💡',
      messageEn: `Low light (${air.light.toFixed(0)}%). Consider supplemental lighting.`,
      messageAr: `إضاءة منخفضة (${air.light.toFixed(0)}%). يُنصح بإضاءة إضافية.`,
      reading: `${air.light.toFixed(0)}%`,
    });
  }

  // attach lang so caller can pick message key
  return recs.map(r => ({ ...r, _lang: lang } as Recommendation & { _lang: string }));
}

interface Props { air: AirReading | undefined }

export default function RecommendationsPanel({ air }: Props) {
  const { t, i18n } = useTranslation();
  if (!air) return null;

  const isAr = i18n.language === 'ar';
  const recs = buildRecommendations(air, t);
  if (recs.length === 0) return null;

  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
      <h2 className="font-bold text-amber-700 mb-3">⚠️ {t('engineer.recommendations')}</h2>
      <ul className="space-y-2">
        {recs.map((rec, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-amber-800">
            <span className="text-base leading-none mt-0.5">{rec.icon}</span>
            <span>{isAr ? rec.messageAr : rec.messageEn}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
