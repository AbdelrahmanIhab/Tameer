import client from './client';
import type {
  LatestSnapshot,
  ZoneSoilResponse,
  ZoneAirResponse,
  HistoryResponse,
  AutomationEventsResponse,
  ManualCommandRequest,
  PlantHealthResult,
} from '../types/api';

export const fetchLatestSnapshot = (zoneId = 1) =>
  client.get<LatestSnapshot>('/sensors/latest', { params: { zone_id: zoneId } }).then(r => r.data);

export const fetchSoilReadings = (zoneId: number) =>
  client.get<ZoneSoilResponse>(`/sensors/soil/latest/${zoneId}`).then(r => r.data);

export const fetchAirReadings = (zoneId: number) =>
  client.get<ZoneAirResponse>(`/sensors/air/latest/${zoneId}`).then(r => r.data);

export const fetchHistory = (zoneId: number, measurement: string, hours: number) =>
  client
    .get<HistoryResponse>(`/sensors/history/${zoneId}`, { params: { measurement, hours } })
    .then(r => r.data);

export const fetchAutomationEvents = (hours = 24) =>
  client.get<AutomationEventsResponse>('/automation/events', { params: { hours } }).then(r => r.data);

export const postManualCommand = (body: ManualCommandRequest) =>
  client.post('/automation/command', body).then(r => r.data);

export const uploadCameraImage = async (zoneId: number, instance: number, file: File) => {
  const form = new FormData();
  form.append('image', file);
  return client.post(`/camera/upload/zone/${zoneId}/camera/${instance}`, form).then(r => r.data);
};

export const analyzeUploadedImage = async (file: File): Promise<PlantHealthResult> => {
  const form = new FormData();
  form.append('image', file);
  return client.post<PlantHealthResult>('/camera/analyze', form).then(r => r.data);
};

export const getCameraImageUrl = (zoneId = 1, instance = 1, bust?: number) => {
  const base = `${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/camera/zone/${zoneId}/camera/${instance}/latest.jpg`;
  return bust ? `${base}?t=${bust}` : base;
};
