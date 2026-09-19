FROM node:20-alpine
WORKDIR /app
COPY src/frontend/package*.json ./
RUN npm install
COPY src/frontend/ .
RUN npm run build
CMD ["npm", "start"]
