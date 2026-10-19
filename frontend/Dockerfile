# The Vite dev server. Development image; the source is mounted by Compose.
# Node runs the tools (Vite+, Vitest, jsdom); Bun installs packages and runs scripts. The official
# Bun image points `node` at Bun, which jsdom doesn't support, so Bun is copied onto Node instead.
FROM node:24-slim

COPY --from=oven/bun:1.4.3 /usr/local/bin/bun /usr/local/bin/bun

WORKDIR /app/frontend
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .

EXPOSE 5173
CMD ["bun", "run", "dev", "--host", "0.0.0.0"]
