# https://hub.docker.com/_/python
FROM python:3.10-buster

ENV PYTHONUNBUFFERED True

# Copy local code to the container image.
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . ./

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt
CMD ["/usr/local/bin/python3", "classify.py"]
