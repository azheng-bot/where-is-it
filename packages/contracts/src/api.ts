export const OBJECT_STATES = [
  "currently_detected",
  "not_currently_detected",
  "identity_uncertain",
] as const;

export type ObjectState = (typeof OBJECT_STATES)[number];
export type ConfidenceLevel = "high" | "medium" | "low";

export const INTERNAL_CONTRACT_VERSION = "v1" as const;
export type InferenceStatus = "ok" | "degraded" | "failed";
export type InternalErrorCode = "service_unavailable" | "deadline_exceeded" | "contract_mismatch" | "invalid_request" | "model_not_ready";

export interface MediaReference {
  uri: string;
  media_type: string;
}

export interface InferenceRequest {
  request_id: string;
  contract_version: typeof INTERNAL_CONTRACT_VERSION;
  deadline_ms: number;
  source: string;
  frame_ref?: MediaReference;
  media_ref?: MediaReference;
  query?: string;
  payload?: Record<string, unknown>;
}

export interface InferenceError {
  code: InternalErrorCode;
  message: string;
  retryable: boolean;
}

export interface InferenceResponse {
  request_id: string;
  contract_version: typeof INTERNAL_CONTRACT_VERSION;
  model_name: string;
  model_version: string;
  status: InferenceStatus;
  result: Record<string, unknown>;
  error?: InferenceError;
}

export interface LocationSummary {
  location_id: string;
  name: string;
  relation?: string;
}

export interface Evidence {
  evidence_id: string;
  image_url: string;
  observed_at: string;
  bounding_box: [number, number, number, number];
}

export interface Prediction {
  location: LocationSummary;
  confidence: ConfidenceLevel;
  score: number;
  basis: string;
  is_inference: true;
}

export interface CatalogObject {
  object_id: string;
  name: string;
  system_name: string;
  category: string;
  aliases: string[];
  state: ObjectState;
  current_location?: LocationSummary;
  last_location?: LocationSummary;
  observed_at?: string;
  confidence: number;
}

export interface QueryResult {
  answer: string;
  status: ObjectState | "clarification" | "not_found";
  object?: CatalogObject;
  predictions: Prediction[];
  evidence?: Evidence;
  clarification_options?: CatalogObject[];
  timings: Record<string, number>;
}
