# Frontend image — build the Vite SPA, serve it (and reverse-proxy /api) via nginx.
# Stage 1: build the static bundle.
FROM node:22-alpine AS build
WORKDIR /app

# Enable pnpm (repo uses pnpm-lock.yaml). Pin the version so the build is
# reproducible regardless of the base image's bundled corepack default.
RUN corepack enable && corepack prepare pnpm@10.32.0 --activate

# Install deps first for layer caching. esbuild's postinstall (native binary)
# is allow-listed via package.json > pnpm.onlyBuiltDependencies.
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build. VITE_RESEARCH_API is left empty so the SPA calls same-origin /api,
# which nginx reverse-proxies to the backend (see nginx.conf).
COPY . .
RUN pnpm build

# Stage 2: nginx serving dist/ + proxying /api.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
