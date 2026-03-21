FROM node:22

WORKDIR /app

# Install pnpm
RUN npm install -g pnpm

# Clean dependencies with every build
RUN rm -rf node_modules package-lock.json pnpm-lock.yaml

# Copy source code
COPY . .

# Install dependencies
RUN CI=true pnpm install

RUN CI=true pnpm install react-router-dom


# Build the Vite + shadcn UI project
RUN pnpm run build

# Expose dev server port
EXPOSE 5173

# Default to dev server; override with `pnpm run build && pnpm run preview` for production
CMD ["pnpm", "run", "dev", "--host"]