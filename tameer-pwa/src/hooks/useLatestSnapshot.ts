import { useQuery } from '@tanstack/react-query';
import { fetchLatestSnapshot } from '../api/endpoints';

export const useLatestSnapshot = (zoneId = 1) =>
  useQuery({
    queryKey: ['snapshot', zoneId],
    queryFn: () => fetchLatestSnapshot(zoneId),
    refetchInterval: 15000,
    staleTime: 10000,
  });
