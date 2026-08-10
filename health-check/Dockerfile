FROM python:3.10-slim

# Install curl, jq, and git (required for dynamic repo updates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    jq \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy main.py script
COPY health-check/main.py /app/main.py

# Install dependencies
RUN pip install --no-cache-dir pyyaml

# Copy huggingface.py, suppliers.py, litellm.py, and zuplo.py
COPY health-check/huggingface.py /app/huggingface.py
COPY health-check/suppliers.py /app/suppliers.py
COPY health-check/litellm.py /app/litellm.py
COPY health-check/zuplo.py /app/zuplo.py

EXPOSE 8000

# Set main.py as the entry point
CMD ["python", "-u", "main.py"]
