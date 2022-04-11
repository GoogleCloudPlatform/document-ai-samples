FROM node:current-slim

COPY . ./

WORKDIR ./Frontend

RUN npm install -g @angular/cli

RUN npm install

RUN npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]