export const OBJECT_STATES = [
  "currently_detected",
  "not_currently_detected",
  "identity_uncertain",
] as const;

export type ObjectState = (typeof OBJECT_STATES)[number];
export type ConfidenceLevel = "high" | "medium" | "low";

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
