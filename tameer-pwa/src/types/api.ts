export interface SoilReading {
  node_id: string;
  moisture: number;
  soil_temp: number;
  ec: number;
  ph: number;
  nitrogen: number;
  phosphorus: number;
  potassium: number;
  dryness_level: 'wet' | 'moderate' | 'dry';
  _time: string;
}

export interface AirReading {
  node_id: string;
  air_temp: number;
  air_humidity: number;
  pressure: number;
  light: number;
  rain: number;
  wind_speed: number;
  wind_direction: number;
  uv_index: number;
  air_quality: number;
  _time: string;
}

export interface LatestSnapshot {
  timestamp: string;
  soil: SoilReading | null;
  weather: AirReading | null;
  image_url: string | null;
  health_status: string | null;
  confidence: number | null;
}

export interface AutomationEvent {
  timestamp: string;
  actuator: string;
  action: string;
  trigger_reason: string;
  node_id: number;
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
  node_id: number;
  measurement: string;
  hours: number;
  count: number;
  data: (SoilReading & AirReading)[];
}

export interface ManualCommandRequest {
  target_node: number;
  actuator: string;
  action: 'on' | 'off';
}

export type ActuatorName =
  | 'irrigation_valve'
  | 'fertilizer_pump'
  | 'fan'
  | 'heater'
  | 'grow_light'
  | 'shade'
  | 'spray_nozzle';
