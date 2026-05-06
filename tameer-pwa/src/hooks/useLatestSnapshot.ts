import { useQuery } from '@tanstack/react-query';
import { fetchLatestSnapshot } from '../api/endpoints';

export const useLatestSnapshot = () =>
  useQuery({ queryKey: ['snapshot'], queryFn: fetchLatestSnapshot });
