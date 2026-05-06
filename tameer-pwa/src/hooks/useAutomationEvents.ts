import { useQuery } from '@tanstack/react-query';
import { fetchAutomationEvents } from '../api/endpoints';

export const useAutomationEvents = (hours = 24) =>
  useQuery({ queryKey: ['events', hours], queryFn: () => fetchAutomationEvents(hours) });
