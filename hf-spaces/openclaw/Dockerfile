# OpenClaw v2026.3.13 — HF Spaces Docker Deployment
FROM node:20-slim

ENV PORT=7860
ENV NODE_ENV=production

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY . .
RUN mkdir -p /data/conversations /data/logs /data/executions && chmod -R 777 /data

EXPOSE 7860
CMD ["node", "server.js"]
