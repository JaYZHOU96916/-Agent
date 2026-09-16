export type Column = { name: string; dtype: string; missing_count: number; missing_fraction: number };
export type Dataset = {
  dataset_id: string; filename: string; row_count: number; column_count: number;
  size_bytes: number; columns: Column[]; sample_rows: Record<string, unknown>[]; warnings: string[];
};
export type EventData = {
  steps?: string[]; code?: string; diff?: string; attempt?: number; stream?: string;
  text?: string; message?: string; recoverable?: boolean; state?: string; status?: string;
  option?: Record<string, unknown>; session_id?: string; cache?: string; repairs?: number;
};
export type StreamEvent = { event: string; data: EventData };
