FROM node:21-slim

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY . ./

# hadolint ignore=DL3000
WORKDIR ./Frontend

RUN npm install && npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]