import { useQuery } from '@tanstack/react-query';
import { fetchHistory } from '../api/endpoints';

export const useHistory = (zoneId: number, measurement: string, hours: number) =>
  useQuery({
    queryKey: ['history', zoneId, measurement, hours],
    queryFn: () => fetchHistory(zoneId, measurement, hours),
    refetchInterval: 60000,
    staleTime: 55000,
  });
