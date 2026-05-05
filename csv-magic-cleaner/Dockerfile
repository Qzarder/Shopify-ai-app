FROM node:20-alpine
RUN apk add --no-cache openssl

EXPOSE 3000

WORKDIR /app

ENV NODE_ENV=production

COPY package.json package-lock.json* ./

RUN npm install && npm cache clean --force

COPY package.json package-lock.json* ./

COPY . .

RUN npm run build

RUN npx prisma generate

CMD ["npm", "run", "start"]
