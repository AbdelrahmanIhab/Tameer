import { useTranslation } from 'react-i18next';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface Props { history: any[] }

export default function MoistureChart({ history }: Props) {
  const { t } = useTranslation();
  const data = history
    .filter(r => r.moisture != null)
    .map((r, i) => ({ i, moisture: Number(r.moisture).toFixed(1) }));

  return (
    <div className="bg-white rounded-xl shadow-sm p-4">
      <h2 className="font-bold text-primary mb-3">{t('engineer.historyChart')}</h2>
      {data.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-8">No history data yet</p>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="i" tick={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [`${v}%`, 'Moisture']} />
            <Line type="monotone" dataKey="moisture" stroke="#2d7a3a" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
