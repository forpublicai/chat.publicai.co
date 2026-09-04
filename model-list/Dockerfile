FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Expose HTTP API port
EXPOSE 8000

# Copy application script
# Wildcard pattern allows building from repository root (context: .) or model-list directory (context: ./model-list)
COPY main.py* model-list/main.py* /app/

# Run the model-list service
CMD ["python", "-u", "main.py"]
