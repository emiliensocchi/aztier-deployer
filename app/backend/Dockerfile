# syntax=docker/dockerfile:1

# Stage 1: install dependencies
FROM cgr.dev/chainguard/python:latest-dev AS build
WORKDIR /app
RUN python -m venv venv
ENV PATH="/app/venv/bin":$PATH
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Stage 2: copy application
FROM cgr.dev/chainguard/python:latest
WORKDIR /app
COPY app.py app.py
COPY --from=build /app/venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
EXPOSE 5000
ENTRYPOINT ["python", "app.py"]