FROM node:20-alpine

WORKDIR /app
RUN apk add --no-cache python3 make g++ krb5-dev

COPY package.json package-lock.json ./
RUN npm install

COPY . .

ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG MONGODB_IP
RUN echo "NEXT_PUBLIC_GOOGLE_MAPS_API_KEY=${NEXT_PUBLIC_GOOGLE_MAPS_API_KEY}" > .env && \
    echo "MONGODB_IP=${MONGODB_IP}" >> .env

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
