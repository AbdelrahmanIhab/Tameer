import client from './client';
import type {
  LatestSnapshot,
  SoilReadingsResponse,
  AirReadingsResponse,
  HistoryResponse,
  AutomationEventsResponse,
  ManualCommandRequest,
} from '../types/api';

export const fetchLatestSnapshot = () =>
  client.get<LatestSnapshot>('/sensors/latest').then(r => r.data);

export const fetchSoilReadings = () =>
  client.get<SoilReadingsResponse>('/sensors/soil/latest').then(r => r.data);

export const fetchAirReadings = () =>
  client.get<AirReadingsResponse>('/sensors/air/latest').then(r => r.data);

export const fetchHistory = (nodeId: number, measurement: string, hours: number) =>
  client
    .get<HistoryResponse>(`/sensors/history/${nodeId}`, { params: { measurement, hours } })
    .then(r => r.data);

export const fetchAutomationEvents = (hours = 24) =>
  client.get<AutomationEventsResponse>('/automation/events', { params: { hours } }).then(r => r.data);

export const postManualCommand = (body: ManualCommandRequest) =>
  client.post('/automation/command', body).then(r => r.data);

export const uploadCameraImage = async (file: File) => {
  const form = new FormData();
  form.append('image', file);
  return client.post('/camera/upload', form).then(r => r.data);
};

export const getCameraImageUrl = (bust?: number) => {
  const base = `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/camera/latest.jpg`;
  return bust ? `${base}?t=${bust}` : base;
};
