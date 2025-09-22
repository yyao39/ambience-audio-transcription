FROM node:20-slim

# Ensure production environment.
ENV NODE_ENV=production

# Set the working directory.
WORKDIR /usr/src/app

# Copy application dependency manifests to the container image.
# A wildcard is used to ensure copying both package.json AND package-lock.json (when available).
# Copying this first prevents re-running npm install on every code change.
COPY package*.json ./

RUN npm ci --omit=dev

# Copy local code to the container image.
COPY . ./

# Expose the port Cloud Run expects.
EXPOSE 8080

# Run the web service on container startup.
CMD [ "node", "asr-server.js" ]