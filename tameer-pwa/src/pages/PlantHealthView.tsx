import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { analyzeUploadedImage } from '../api/endpoints';
import type { PlantHealthResult } from '../types/api';

export default function PlantHealthView() {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlantHealthResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
    const reader = new FileReader();
    reader.onload = ev => setPreview(ev.target?.result as string);
    reader.readAsDataURL(f);
  }

  async function handleAnalyze() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeUploadedImage(file);
      setResult(res);
    } catch {
      setError(t('common.error'));
    } finally {
      setLoading(false);
    }
  }

  const isHealthy = !result || result.disease_class === 'healthy' || result.disease_class === 'pending';

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-primary">{t('plantHealth.title')}</h1>

      <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          onClick={() => inputRef.current?.click()}
          className="w-full py-3 border-2 border-dashed border-gray-300 rounded-xl text-gray-500 text-sm hover:border-primary hover:text-primary transition-colors"
        >
          {t('plantHealth.upload')}
        </button>

        {preview && (
          <img src={preview} alt="Plant preview" className="w-full h-56 object-cover rounded-xl" />
        )}

        {file && !loading && (
          <button
            onClick={handleAnalyze}
            className="w-full py-2 bg-primary text-white font-semibold rounded-xl hover:bg-primary/90 transition-colors"
          >
            {t('plantHealth.analyzing').replace('...', '')} →
          </button>
        )}

        {loading && (
          <p className="text-center text-primary font-semibold text-sm py-2">{t('plantHealth.analyzing')}</p>
        )}

        {error && (
          <p className="text-center text-red-500 text-sm">{error}</p>
        )}
      </div>

      {result ? (
        <div className="bg-white rounded-xl shadow-sm p-4 space-y-3">
          <h2 className="font-bold text-primary">{t('plantHealth.result')}</h2>

          {result.stub && (
            <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
              {t('plantHealth.stubNotice')}
            </p>
          )}

          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-semibold ${isHealthy ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}`}>
              {result.disease_class}
            </span>
            <span className="text-xs text-gray-400">{t('plantHealth.diseaseClass')}</span>
          </div>

          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">{t('plantHealth.confidence')}</span>
              <span className="font-semibold">{(result.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">{t('plantHealth.healthScore')}</span>
              <span className="font-semibold">{(result.health_score * 100).toFixed(0)}%</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all ${isHealthy ? 'bg-green-500' : 'bg-orange-500'}`}
                style={{ width: `${result.health_score * 100}%` }}
              />
            </div>
          </div>
        </div>
      ) : (
        !loading && (
          <p className="text-center text-gray-400 text-sm py-6">{t('plantHealth.noResult')}</p>
        )
      )}
    </div>
  );
}
