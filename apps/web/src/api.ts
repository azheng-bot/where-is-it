import type { CatalogObject, QueryResult } from "@where-is-it/contracts";

const baseUrl = "http://127.0.0.1:8000";

export async function getObjects(): Promise<CatalogObject[]> {
  const response = await fetch(`${baseUrl}/api/objects`);
  if (!response.ok) throw new Error("无法获取物品目录");
  return response.json();
}

export async function getLocations() {
  const response = await fetch(`${baseUrl}/api/locations`);
  if (!response.ok) throw new Error("无法获取位置目录");
  return response.json() as Promise<Array<{ location_id: string; name: string; item_count: number }>>;
}

export interface RoomState { camera: { status: string; label: string; updated_at: string; frame_url: string; stream_url?: string; source_kind?: string }; catalog: { objects: number; locations: number }; vision: { status: string; profile: string } }

export async function getRoomState(): Promise<RoomState> {
  const response = await fetch(`${baseUrl}/api/room/state`);
  if (!response.ok) throw new Error("无法获取摄像头状态");
  return response.json();
}
export async function askQuestion(text: string): Promise<QueryResult> {
  const response = await fetch(`${baseUrl}/api/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
  if (!response.ok) throw new Error("查询服务暂时不可用");
  return response.json();
}

export async function renameObject(id: string, name: string, aliases: string[]) {
  const response = await fetch(`${baseUrl}/api/objects/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, aliases }) });
  if (!response.ok) throw new Error((await response.json()).detail ?? "修改失败");
  return response.json() as Promise<CatalogObject>;
}

export interface TranscriptionResult {
  text: string;
  provider: string;
  status: "success" | "failed";
  model_version?: string;
  language?: string;
  confidence?: number;
  error_code?: string;
}

export async function transcribeAudio(audio: Blob): Promise<TranscriptionResult> {
  const form = new FormData();
  form.append("audio", audio, "question.webm");
  const response = await fetch(`${baseUrl}/api/speech/transcribe`, { method: "POST", body: form });
  if (!response.ok) throw new Error("语音服务暂时不可用");
  const result = await response.json() as TranscriptionResult;
  if (result.status !== "success") throw new Error(result.error_code ?? "语音转写失败");
  return result;
}