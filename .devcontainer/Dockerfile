# Base image from Devcontainers Microsoft repository
FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04

# Install basic Linux utilities and development dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        curl \
        wget \
        git \
        build-essential \
        ca-certificates \
        jq \
        unzip \
        htop \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set default timezone
ENV TZ=Asia/Shanghai
