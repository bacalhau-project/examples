FROM node:20-alpine

WORKDIR /app
RUN apk add --no-cache python3 make g++ krb5-dev

COPY package.json package-lock.json ./
RUN npm install

COPY . .

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ARG NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
ARG FERRETDB_URI


#RUN npm run build
EXPOSE 3000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["npm", "run", "dev"]
