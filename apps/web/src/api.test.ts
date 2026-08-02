import { afterEach, expect, test, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

test("uses the configured public API address", async () => {
  vi.stubEnv("VITE_API_BASE_URL", "https://gpu.example.com/");
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);

  const { getObjects } = await import("./api");
  await getObjects();

  expect(fetchMock).toHaveBeenCalledWith("https://gpu.example.com/api/objects");
});