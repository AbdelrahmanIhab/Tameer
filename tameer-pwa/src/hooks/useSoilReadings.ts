import { useQuery } from '@tanstack/react-query';
import { fetchSoilReadings } from '../api/endpoints';

export const useSoilReadings = (zoneId: number) =>
  useQuery({
    queryKey: ['soil', zoneId],
    queryFn: () => fetchSoilReadings(zoneId),
    refetchInterval: 15000,
    staleTime: 10000,
  });
