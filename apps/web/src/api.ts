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
