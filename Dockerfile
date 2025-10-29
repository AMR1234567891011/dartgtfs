# Base image with Python 3.12 and essential Linux tools
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install dependencies needed for Playwright and GUI forwarding
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl git unzip vim less \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libx11-xcb1 libxtst6 libxshmfence1 xvfb x11-apps \
    && rm -rf /var/lib/apt/lists/*
# Install Python dependencies
RUN pip install --no-cache-dir \
    playwright \
    pandas \
    protobuf \
    ipython \
    jupyterlab \
    google \
    gtfs_realtime_pb2 \
    zmq \
    pytz 
# Install Playwright browsers (Chromium, Firefox, WebKit)
RUN playwright install --with-deps chromium
# Set working directory inside container
WORKDIR /workspace
# Copy the *entire project directory* (where the Dockerfile is) into the container
COPY . /workspace
# Expose ports for development (Jupyter, FastAPI, etc.)
EXPOSE 8080
EXPOSE 8888
# Default shell
CMD ["/bin/bash"]
# docker build -t dart-dev .
# docker run -it --rm \
#   -e DISPLAY=$DISPLAY \
#   -v /tmp/.X11-unix:/tmp/.X11-unix \
#   -v $(pwd):/workspace \
#   -p 8080:8080 -p 8888:8888 -p5556:5556\
#   dart-dev
