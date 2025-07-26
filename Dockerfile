FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install basic development tools
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    curl \
    wget \
    vim \
    nano \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Set up a non-root user for added security
RUN useradd -ms /bin/bash agent
USER agent
WORKDIR /workspace

# Keep container alive
CMD ["tail", "-f", "/dev/null"]