FROM node:20-alpine

WORKDIR /app

# Install dependencies (layer cached until package-lock.json changes)
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code
COPY . .

# next.config.js calls rewrites() at build time and bakes the result into
# .next/routes-manifest.json.  BACKEND_URL must therefore be set HERE so the
# server-side proxy points at the correct service on the Docker network.
# The default below is used for standalone (non-Docker) builds.
ARG BACKEND_URL=http://localhost:8000
ENV BACKEND_URL=$BACKEND_URL

RUN npm run build

# Bind to all interfaces so Docker can expose port 3000 to the host.
ENV HOSTNAME="0.0.0.0"

EXPOSE 3000

CMD ["npm", "run", "start"]
