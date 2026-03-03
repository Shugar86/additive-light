# GDI Sandbox - Secure execution environment for LLM-generated code
# This container runs build123d code in isolation

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create non-root user for security
RUN useradd -m -u 1000 gdi && \
    mkdir -p /workspace && \
    chown gdi:gdi /workspace

USER gdi
WORKDIR /workspace

# Copy execution script
COPY execute.py /workspace/

# Default command runs the execute script
ENTRYPOINT ["python", "/workspace/execute.py"]
