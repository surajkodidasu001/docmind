# Multi-stage build: compile the Vite app, then serve the static output with
# nginx. Not validated against a real `docker build` in this sandbox (no
# Docker daemon / no registry access here) — the npm build and lint steps
# it depends on ARE verified (see the "frontend" CI job and this repo's own
# `npm run build` output).
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
