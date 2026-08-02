FROM node:22-bookworm-slim AS build
WORKDIR /workspace

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/contracts/package.json packages/contracts/package.json
RUN corepack enable && pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages/contracts packages/contracts
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ARG VITE_VISION_BASE_URL
ENV VITE_VISION_BASE_URL=${VITE_VISION_BASE_URL}
RUN pnpm --filter @where-is-it/web build

FROM nginx:1.27-alpine
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
EXPOSE 80
