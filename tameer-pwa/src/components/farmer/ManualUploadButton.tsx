import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { uploadCameraImage } from '../../api/endpoints';

export default function ManualUploadButton() {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState<'idle' | 'ok' | 'err'>('idle');
  const qc = useQueryClient();

  const handleChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setStatus('idle');
    try {
      await uploadCameraImage(file);
      qc.invalidateQueries({ queryKey: ['snapshot'] });
      setStatus('ok');
    } catch {
      setStatus('err');
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-2">
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={handleChange} />
      <button
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        className="w-full bg-primary text-white rounded-xl py-3 font-semibold disabled:opacity-50 hover:bg-green-800 transition-colors"
      >
        {uploading ? '⏳ Uploading…' : `📷 ${t('farmer.checkPlant')}`}
      </button>
      {status === 'ok' && <p className="text-green-600 text-sm text-center">✓ {t('farmer.uploadSuccess')}</p>}
      {status === 'err' && <p className="text-red-500 text-sm text-center">✗ {t('farmer.uploadFailed')}</p>}
    </div>
  );
}
