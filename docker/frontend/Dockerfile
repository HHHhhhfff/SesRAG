FROM node:20-alpine

WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
# 构建缓存仅保存公开依赖，不进入镜像；下载故障后可复用已校验的tarball，避免重复从零下载。
RUN --mount=type=cache,id=sesrag-frontend-npm,target=/root/.npm \
    npm ci --prefer-offline --no-audit --no-fund --maxsockets=5 \
    --fetch-retries=3 --fetch-retry-mintimeout=2000 --fetch-retry-maxtimeout=10000 --fetch-timeout=120000
COPY frontend ./

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

