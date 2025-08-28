# syntax=docker/dockerfile:1

FROM cgr.dev/chainguard/nginx:latest

WORKDIR /usr/share/nginx/html
COPY index.html ./
COPY style.css ./
COPY main.js ./
COPY images ./images
COPY config.json ./

EXPOSE 8080
ENTRYPOINT [ "nginx", "-g", "daemon off;" ]