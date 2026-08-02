# Three-service deployment map

| Deployable package | Runs on | Public configuration | Private dependencies | Persistent data |
| --- | --- | --- | --- | --- |
| `video-streamer` | Camera-side edge device | `FRAME_INGEST_URL`, `VISION_PUSH_TOKEN` | Camera adapter only | None; failed frames are discarded |
| `gpu-inference-api` | GPU node | `GPU_API_PORT`, `GPU_VISION_PORT`, `WEB_ALLOWED_ORIGINS`, `VISION_PUSH_TOKEN` | Vision receiver, Florence, Grounding, SAM, Embedding, ASR | `api-data`, `model-cache` volumes |
| `web` | Static-site or web host | `PUBLIC_API_URL` | None | None |

The browser calls only `PUBLIC_API_URL`. The camera-side service calls only
`FRAME_INGEST_URL`. API, vision and ASR use Compose-internal DNS names inside the
GPU package. Do not add host-port mappings for model or ASR containers.

## Health checks

- Video streamer: `GET /health/live` and `GET /health/ready` on its optional health port.
- GPU package: `GET /health/ready` on API port 8000 aggregates API, receiver and ASR availability; receiver health is available on the protected GPU service endpoint for operations.
- Web: an HTTP request to `/` confirms the static package is serving; API configuration is checked at build and by `pnpm topology:check`.

## Compatibility and rollback

The root Compose files remain the compatibility-oriented local multi-process
configuration. The three `deploy/` packages are the supported deployment
interface. Since the GPU package keeps the existing `api-data` volume layout,
rollback only requires pointing Web and the streamer back to the previous API and
receiver URLs; it does not migrate or rewrite the database.