FROM node:12-slim

WORKDIR ./

COPY . ./

RUN cd ./Frontend

RUN npm install && npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]