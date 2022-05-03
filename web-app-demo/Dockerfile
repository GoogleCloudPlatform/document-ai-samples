FROM node:12-slim

COPY . ./

# hadolint ignore=DL3000
WORKDIR ./Frontend

RUN npm install -g @angular/cli

RUN npm install

RUN npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]