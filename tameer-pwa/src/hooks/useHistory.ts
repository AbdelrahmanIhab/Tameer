import { useQuery } from '@tanstack/react-query';
import { fetchHistory } from '../api/endpoints';

export const useHistory = (nodeId: number, measurement: string, hours: number) =>
  useQuery({
    queryKey: ['history', nodeId, measurement, hours],
    queryFn: () => fetchHistory(nodeId, measurement, hours),
    refetchInterval: 60000,
    staleTime: 55000,
  });
