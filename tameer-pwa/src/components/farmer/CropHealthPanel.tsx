import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { LatestSnapshot } from '../../types/api';
import { getCameraImageUrl } from '../../api/endpoints';

interface Props { snapshot: LatestSnapshot | undefined }

export default function CropHealthPanel({ snapshot }: Props) {
  const { t } = useTranslation();
  const [bust] = useState(() => Date.now());
  const imageUrl = snapshot?.image_url ?? getCameraImageUrl(1, 1, bust);
  const health = snapshot?.health_status;
  const confidence = snapshot?.confidence;
  const isHealthy = !health || health.toLowerCase() === 'healthy';

  return (
    <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
      <h2 className="font-bold text-primary">{t('farmer.cropHealth')}</h2>
      {imageUrl ? (
        <img src={imageUrl} alt="Crop" className="w-full h-52 object-cover rounded-lg" />
      ) : (
        <div className="w-full h-40 bg-gray-100 rounded-lg flex items-center justify-center text-gray-400 text-sm">
          {t('farmer.noImage')}
        </div>
      )}
      {health && (
        <div className="flex items-center gap-2">
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${isHealthy ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
            {health}
          </span>
          {confidence != null && (
            <span className="text-xs text-gray-400">{(confidence * 100).toFixed(0)}% confidence</span>
          )}
        </div>
      )}
      {!health && <p className="text-sm text-primary font-semibold">{t('farmer.healthy')}</p>}
    </div>
  );
}
