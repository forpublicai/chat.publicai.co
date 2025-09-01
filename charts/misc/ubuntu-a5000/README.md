# Ubuntu A5000 vLLM Setup

Easy deployment of Apertus models on Ubuntu with A5000 GPU for integration with your existing litellm setup.

## Quick Start

1. **Clone this directory to your Ubuntu A5000 instance:**
   ```bash
   scp -r ubuntu-a5000/ user@your-gpu-instance:~/
   cd ~/ubuntu-a5000/
   ```

2. **Run initial setup:**
   ```bash
   ./setup.sh setup
   ```
   This will install Docker, NVIDIA Docker support, and create the environment file.

3. **Configure environment:**
   Edit `.env` with your settings:
   ```bash
   cp .env.example .env
   nano .env
   ```
   Set:
   - `VLLM_API_KEY` - same key used in your main litellm setup
   - `HF_TOKEN` - your Hugging Face token
   - `PUBLIC_HOST` - the public IP/domain of this instance

4. **Download models:**
   ```bash
   ./setup.sh download
   ```

5. **Start services:**
   ```bash
   ./setup.sh start
   ```

6. **Check status:**
   ```bash
   ./setup.sh status
   ./setup.sh logs
   ```

## Integration with Your Existing LiteLLM

Add these entries to your litellm configuration (`charts/web_services/charts/litellm/values.yaml`):

```yaml
config:
  models:
    # Your existing models...
    
    # External Apertus 8B from Ubuntu A5000 instance
    - model_name: swiss-ai/apertus-8b-external
      litellm_params:
        model: openai/apertus-8b
        api_base: http://YOUR_GPU_INSTANCE_IP/v1  # or https:// if SSL configured
        api_key: "os.environ/VLLM_API_KEY"
```

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Your AWS     │    │  Ubuntu A5000    │    │   End Users     │
│   LiteLLM       │────│   vLLM Instance  │    │                 │
│   (Existing)    │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        │                        │                        │
    Internal                External API              HTTP/HTTPS
    Bedrock +               (port 80/443)              Requests
    vLLM Models                   │                        │
                                  │                        │
                            ┌─────────────┐                │
                            │   Docker    │◄───────────────┘
                            │ ┌─────────┐ │
                            │ │ vLLM    │ │
                            │ │ Apertus │ │
                            │ └─────────┘ │
                            │ ┌─────────┐ │
                            │ │ Nginx   │ │
                            │ │ Proxy   │ │
                            │ └─────────┘ │
                            └─────────────┘
                                  │
                            ┌─────────────┐
                            │  A5000 GPU  │
                            └─────────────┘
```

## Available Commands

- `./setup.sh setup` - Install system dependencies  
- `./setup.sh download` - Download Apertus models
- `./setup.sh start` - Start vLLM services
- `./setup.sh stop` - Stop services
- `./setup.sh status` - Show service status
- `./setup.sh logs` - Show real-time logs
- `./setup.sh cleanup` - Remove everything

## Configuration Options

### Docker Compose
- **8B Model**: Runs on single GPU, ~16GB VRAM
- **70B Model**: Commented out by default (requires ~48GB+ VRAM)
- **Nginx**: Provides load balancing, rate limiting, SSL termination

### Security
- API key authentication matches your existing setup
- Rate limiting via Nginx (10 requests/sec default)
- Optional SSL certificate support

### Resource Requirements
- **A5000 (24GB VRAM)**: Perfect for 8B model
- **Disk Space**: ~50GB for models + containers
- **RAM**: 32GB+ recommended
- **Network**: Stable connection to your AWS region

## Troubleshooting

1. **GPU not detected**: Ensure NVIDIA drivers installed
   ```bash
   nvidia-smi
   sudo apt install nvidia-driver-535  # or latest
   ```

2. **Model download fails**: Check HF_TOKEN and internet connection

3. **Out of memory**: Reduce `--gpu-memory-utilization` in docker-compose.yml

4. **Connection issues**: Check firewall rules:
   ```bash
   sudo ufw allow 80
   sudo ufw allow 443
   ```

## Production Considerations

1. **SSL/TLS**: Configure SSL certificates in nginx.conf
2. **Firewall**: Restrict access to your AWS IP ranges
3. **Monitoring**: Add Prometheus/Grafana for monitoring  
4. **Backups**: Regular backup of model configurations
5. **Updates**: Pin Docker image versions for stability