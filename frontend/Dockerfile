# ----------------------------------------------------
# Stage 1: Build production static assets
# ----------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Cache package dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source and build static artifacts
COPY . .
RUN npm run build

# ----------------------------------------------------
# Stage 2: Serve with Nginx Reverse Proxy
# ----------------------------------------------------
FROM nginx:alpine

# Replace default configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 5173 80

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5173/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

