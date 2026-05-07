export interface SoilReading {
  zone_id: string;
  node_instance: string;
  moisture: number;
  soil_temp: number;
  dryness_level: 'wet' | 'moderate' | 'dry';
  _time: string;
}

export interface AirReading {
  zone_id: string;
  node_instance: string;
  air_temp: number;
  air_humidity: number;
  light: number;
  air_quality: number;
  _time: string;
}

export interface LatestSnapshot {
  timestamp: string | null;
  soil: SoilReading | null;
  weather: AirReading | null;
  image_url: string | null;
  health_status: string | null;
  confidence: number | null;
  irrigation_minutes: number | null;
}

export interface AutomationEvent {
  timestamp: string;
  actuator: string;
  action: string;
  trigger_reason: string;
  zone_id: number;
}

export interface AutomationEventsResponse {
  status: string;
  count: number;
  events: AutomationEvent[];
}

export interface SoilReadingsResponse {
  status: string;
  data: SoilReading[];
}

export interface AirReadingsResponse {
  status: string;
  data: AirReading[];
}

export interface HistoryResponse {
  status: string;
  zone_id: number;
  measurement: string;
  hours: number;
  count: number;
  data: (SoilReading | AirReading)[];
}

export interface ManualCommandRequest {
  target_node: number;
  actuator: 'irrigation_valve';
  action: 'on' | 'off';
}

export interface PlantHealthResult {
  disease_class: string;
  confidence: number;
  health_score: number;
  stub?: boolean;
}

export type ActuatorName = 'irrigation_valve';
