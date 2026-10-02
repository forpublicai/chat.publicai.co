FROM python:3.12-slim
RUN pip install --no-cache-dir 'litellm[proxy]==1.98.0'
EXPOSE 4000
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
