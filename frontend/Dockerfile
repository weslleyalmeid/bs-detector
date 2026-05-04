FROM node:20-slim

WORKDIR /app

# Install deps first so layer caches when only source changes.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5175

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
