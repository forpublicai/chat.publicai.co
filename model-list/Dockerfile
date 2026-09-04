FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install dependencies
COPY requirements.txt* model-list/requirements.txt* /app/
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; else pip install --no-cache-dir fastapi uvicorn pyyaml httpx; fi

# Expose HTTP API port
EXPOSE 8000

# Copy application script
COPY main.py* model-list/main.py* /app/

# Run the model-list service
CMD ["python", "-u", "main.py"]
