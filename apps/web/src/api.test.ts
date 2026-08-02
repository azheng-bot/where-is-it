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
test("uses the configured public vision address for the fallback frame", async () => {
  vi.stubEnv("VITE_VISION_BASE_URL", "https://vision.example.com/");

  const { defaultCameraFrameUrl } = await import("./api");

  expect(defaultCameraFrameUrl).toBe("https://vision.example.com/api/camera/latest.jpg");
});