FROM node:12-slim

WORKDIR /Frontend/.

COPY . ./

RUN npm install && npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]