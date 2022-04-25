FROM node:12-slim

WORKDIR /web-app-demo/Frontend

COPY . ./

RUN npm install -g @angular/cli

RUN npm install

RUN npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]