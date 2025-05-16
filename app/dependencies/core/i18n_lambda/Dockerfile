FROM node:22

# Install zip
RUN apt-get update && apt-get install -y zip

WORKDIR /app

COPY index.js .

RUN zip -r9 /lambda.zip .
