const endpoints = [
  ["video streamer", process.env.VIDEO_STREAMER_URL ?? "http://127.0.0.1:8001/health/ready"],
  ["GPU API", process.env.GPU_API_URL ?? "http://127.0.0.1:8000/health/ready"],
  ["web", process.env.WEB_URL ?? "http://127.0.0.1:5173/"],
];

for (const [name, url] of endpoints) {
  let response;
  try {
    response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  } catch (error) {
    throw new Error(`${name} is unreachable at ${url}: ${error.message}`);
  }
  if (!response.ok) throw new Error(`${name} failed health check at ${url}: HTTP ${response.status}`);
  console.log(`${name}: ${response.status}`);
}