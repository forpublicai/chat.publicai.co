echo "ARGO"
echo "username admin"
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo ""


echo "LITELLM MASTER KEY"
kubectl get secret litellm-secrets -n web-services -o jsonpath='{.data.litellm_master_key}' | base64 -d
