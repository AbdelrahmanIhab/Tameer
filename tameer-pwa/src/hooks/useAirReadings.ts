import { useQuery } from '@tanstack/react-query';
import { fetchAirReadings } from '../api/endpoints';

export const useAirReadings = (zoneId: number) =>
  useQuery({
    queryKey: ['air', zoneId],
    queryFn: () => fetchAirReadings(zoneId),
    refetchInterval: 15000,
    staleTime: 10000,
  });
