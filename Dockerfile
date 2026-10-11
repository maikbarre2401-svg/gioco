FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
COPY config ./config
ENV NODE_ENV=production
EXPOSE 3000
# data/ contiene la sessione WhatsApp e la memoria: montala come volume
VOLUME ["/app/data"]
CMD ["node", "src/index.js"]
