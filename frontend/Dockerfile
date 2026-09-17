# Build from this directory:  docker build -t rag-frontend ./frontend
# (compose builds it with context: ./frontend — see ../docker-compose.yml)
FROM node:24-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# Not `npm ci`: Tailwind v4's oxide binary and its emnapi wasm fallback resolve
# different optional native packages on Windows (where this lockfile is
# generated) vs this Linux image, and `npm ci` refuses that mismatch outright.
RUN npm install

FROM node:24-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# API_URL is read at REQUEST time (lib/api.ts), not baked in here — nothing
# backend-specific needs to be known at build time.
RUN npm run build

# next.config.ts sets output: "standalone", so .next/standalone already carries
# its own minimal node_modules — the runner never needs deps/ or a full install.
FROM node:24-slim AS runner
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
# node:24-slim already ships a "node" user at uid 1000 - reuse it.
USER node

EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD node -e "fetch('http://localhost:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
