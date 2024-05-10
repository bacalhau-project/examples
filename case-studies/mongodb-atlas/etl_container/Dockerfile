# Use an official Node.js runtime as a parent image
FROM node:20.12.2-buster

WORKDIR /app

COPY etl.js .
COPY package.json .

RUN npm i

# Run the script when the container launches
CMD ["node", "etl.js"]
