FROM node:12-slim

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

RUN cd ./Frontend

RUN npm install && npm run build

EXPOSE 8080

CMD [ "node", "server.js" ]