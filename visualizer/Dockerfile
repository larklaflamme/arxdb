# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the SvelteKit app (adapter-node → self-contained Node server).
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — runtime: Node server + the built app.
# ---------------------------------------------------------------------------
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app/build ./build
COPY --from=build /app/package.json ./
COPY --from=build /app/node_modules ./node_modules

# The backend URL is a runtime concern (set via docker-compose / -e), so the
# same image can point at any ArxDB deployment without a rebuild.
ENV ARXDB_API_URL=http://arxdb:8080 \
    PORT=3000

EXPOSE 3000
CMD ["node", "build"]
