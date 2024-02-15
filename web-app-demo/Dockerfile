FROM node:21-slim

# Specify a non-root user
USER node

ENV APP_HOME /app
WORKDIR $APP_HOME

COPY . ./

# Specify a non-root user
USER node

# Change WORKDIR to an absolute path
WORKDIR /app/Frontend

RUN npm install && npm run build

# Add a HEALTHCHECK instruction
HEALTHCHECK CMD curl --fail http://localhost/ || exit 1

EXPOSE 8080

CMD [ "node", "server.js" ]
