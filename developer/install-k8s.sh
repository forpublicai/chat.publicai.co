#!/bin/bash

# Exit on error, undefined var, or failed pipe
set -Eeuo pipefail

LOG_FILE="errors.log"

# Clear previous log
: > "$LOG_FILE"

# Error handler
error_handler() {
  local exit_code=$?
  local line_no=$1
  echo "[ERROR] Exit code $exit_code at line $line_no" | tee -a "$LOG_FILE"
}

trap 'error_handler $LINENO' ERR

# Run command helper (prints + logs command)
run_cmd() {
  echo "[RUN] $*" | tee -a "$LOG_FILE"
  "$@" 2>&1 | tee -a "$LOG_FILE"
}

sudo k0s stop || true
sudo k0s reset || true
run_cmd curl --proto '=https' --tlsv1.2 -sSf https://get.k0s.sh | sudo sh
run_cmd sudo k0s install controller --enable-worker --no-taints
run_cmd sudo k0s start

sleep 40


#K0S_CONTEXT_NAME="publicai-local"
 #K0S_KUBECONFIG="$(mktemp)"
 #
 #sudo k0s kubeconfig admin > "$K0S_KUBECONFIG"
 #
 #KUBECONFIG="$K0S_KUBECONFIG" kubectl config rename-context Default "$K0S_CONTEXT_NAME"
 #
 #mkdir -p "$HOME/.kube"
 #touch "$HOME/.kube/config"
 #
 #KUBECONFIG="$HOME/.kube/config:$K0S_KUBECONFIG" kubectl config view --flatten > "$HOME/.kube/config.tmp"
 #mv "$HOME/.kube/config.tmp" "$HOME/.kube/config"
 #
 #kubectl config use-context "$K0S_CONTEXT_NAME"
 #
 #rm "$K0S_KUBECONFIG"
run_cmd bash -c "sudo k0s kubeconfig admin > ~/.kube/config"
kubectl config rename-context Default publicai-local

echo "Installing storage" | tee -a "$LOG_FILE"

run_cmd helm repo add sig-storage-local-static-provisioner https://kubernetes-sigs.github.io/sig-storage-local-static-provisioner
run_cmd helm repo update

run_cmd bash -c "helm template --debug sig-storage-local-static-provisioner/local-static-provisioner \
  --version 2.8.0 \
  --namespace kube-system \
  --values storage-config.yaml \
  > local-volume-provisioner.generated.yaml"

run_cmd kubectl create -f local-volume-provisioner.generated.yaml
sleep 30
run_cmd kubectl patch storageclass local-storage -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

run_cmd kubectl apply -f external-db-services.yaml
