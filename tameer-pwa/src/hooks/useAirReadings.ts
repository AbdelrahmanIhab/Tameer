import { useQuery } from '@tanstack/react-query';
import { fetchAirReadings } from '../api/endpoints';

export const useAirReadings = () =>
  useQuery({ queryKey: ['air'], queryFn: fetchAirReadings });
