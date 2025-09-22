# Use the official lightweight Node.js 18 image.
FROM node:18-slim AS base

# Ensure production environment.
ENV NODE_ENV=production

# Set the working directory.
WORKDIR /usr/src/app

# Install dependencies first to take advantage of cached layers.
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Copy the rest of the application source.
COPY . .

# Expose the port Cloud Run expects.
EXPOSE 8080

# Start the service.
CMD ["npm", "start"]