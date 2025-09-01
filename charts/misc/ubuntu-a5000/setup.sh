#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to show usage
show_usage() {
    echo "Ubuntu A5000 vLLM Setup Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup       Install dependencies and prepare system"
    echo "  download    Download Apertus models"
    echo "  start       Start vLLM services"
    echo "  stop        Stop vLLM services"  
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  cleanup     Remove all services and data"
    echo ""
    exit 1
}

# Check if running as root for system setup
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root. Please run as a regular user with sudo access."
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    print_info "Installing system dependencies..."
    
    # Update system
    sudo apt update && sudo apt upgrade -y
    
    # Install Docker
    if ! command -v docker &> /dev/null; then
        print_info "Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
        print_warning "Docker installed. Please log out and log back in, then run this script again."
        exit 0
    fi
    
    # Install Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_info "Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    fi
    
    # Install NVIDIA Docker support
    if ! dpkg -l | grep -q nvidia-docker2; then
        print_info "Installing NVIDIA Docker support..."
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID) && \
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg && \
        curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
        
        sudo apt update && sudo apt install -y nvidia-docker2
        sudo systemctl restart docker
    fi
    
    # Install other useful tools
    sudo apt install -y curl wget git htop nvidia-smi
    
    print_status "Dependencies installed successfully!"
}

# Verify NVIDIA GPU
verify_gpu() {
    print_info "Checking NVIDIA GPU..."
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi
        print_status "GPU detected successfully!"
    else
        print_error "NVIDIA drivers not found. Please install NVIDIA drivers first."
        exit 1
    fi
}

# Setup environment
setup_environment() {
    print_info "Setting up environment..."
    
    # Create .env file if it doesn't exist
    if [ ! -f ".env" ]; then
        cp .env.example .env
        print_warning "Created .env file. Please edit it with your configuration before proceeding."
        print_info "Required variables:"
        print_info "  - VLLM_API_KEY: API key for vLLM authentication"
        print_info "  - HF_TOKEN: Hugging Face token for model downloads"
        print_info "  - PUBLIC_HOST: Public hostname/IP for this instance"
        exit 0
    fi
    
    # Source environment variables
    source .env
    
    # Validate required variables
    if [ -z "$VLLM_API_KEY" ]; then
        print_error "VLLM_API_KEY is required in .env file"
        exit 1
    fi
    
    # Create models directory
    mkdir -p models ssl
    
    print_status "Environment setup complete!"
}

# Download models
download_models() {
    print_info "Downloading Apertus models..."
    
    # Source environment
    source .env
    
    if [ -z "$HF_TOKEN" ]; then
        print_warning "HF_TOKEN not set. Attempting to download without authentication..."
    fi
    
    # Download 8B model
    if [ ! -d "models/Apertus-8B-aligned-branded" ]; then
        print_info "Downloading Apertus 8B model..."
        docker run --rm -v "$(pwd)/models:/models" \
            -e HF_TOKEN="$HF_TOKEN" \
            huggingface/transformers-pytorch-gpu \
            python -c "
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
model_name = 'swiss-ai/apertus-8b-aligned-branded'
save_path = '/models/Apertus-8B-aligned-branded'
print(f'Downloading {model_name} to {save_path}...')
tokenizer = AutoTokenizer.from_pretrained(model_name, use_auth_token=os.environ.get('HF_TOKEN'))
model = AutoModelForCausalLM.from_pretrained(model_name, use_auth_token=os.environ.get('HF_TOKEN'))
tokenizer.save_pretrained(save_path)
model.save_pretrained(save_path)
print('Download complete!')
"
    else
        print_info "Apertus 8B model already exists"
    fi
    
    # Optionally download 70B model (requires significant space and memory)
    # print_info "For 70B model, uncomment the relevant section in docker-compose.yml"
    
    print_status "Model download complete!"
}

# Start services
start_services() {
    print_info "Starting vLLM services..."
    
    # Check if .env exists
    if [ ! -f ".env" ]; then
        print_error ".env file not found. Run 'setup' command first."
        exit 1
    fi
    
    # Pull latest images
    docker-compose pull
    
    # Start services
    docker-compose up -d
    
    print_status "Services started!"
    print_info "vLLM API available at: http://localhost:8000"
    print_info "Nginx proxy available at: http://localhost"
    print_info "Use 'logs' command to monitor startup progress"
}

# Stop services
stop_services() {
    print_info "Stopping vLLM services..."
    docker-compose down
    print_status "Services stopped!"
}

# Show status
show_status() {
    print_info "Service status:"
    docker-compose ps
    echo ""
    print_info "System resources:"
    docker stats --no-stream
}

# Show logs
show_logs() {
    docker-compose logs -f
}

# Cleanup everything
cleanup_services() {
    print_warning "This will remove all containers, images, and downloaded models!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."
        docker-compose down -v --rmi all
        sudo rm -rf models/*
        print_status "Cleanup complete!"
    else
        print_info "Cleanup cancelled"
    fi
}

# Main script logic
case "$1" in
    "setup")
        check_root
        verify_gpu
        install_dependencies
        setup_environment
        ;;
    "download")
        download_models
        ;;
    "start")
        start_services
        ;;
    "stop")
        stop_services
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "cleanup")
        cleanup_services
        ;;
    *)
        show_usage
        ;;
esac