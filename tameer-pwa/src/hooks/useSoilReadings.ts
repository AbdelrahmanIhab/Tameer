import { useQuery } from '@tanstack/react-query';
import { fetchSoilReadings } from '../api/endpoints';

export const useSoilReadings = () =>
  useQuery({ queryKey: ['soil'], queryFn: fetchSoilReadings });
