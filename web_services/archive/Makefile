.PHONY: deploy cleanup status logs

# Deploy everything (like docker-compose up)
deploy:
	@echo "🚀 Deploying Open WebUI..."
	./deploy.sh

# Remove everything (like docker-compose down)
cleanup:
	@echo "🧹 Cleaning up..."
	./cleanup.sh

# Check status (like docker-compose ps)
status:
	@echo "📊 Deployment Status:"
	@echo ""
	@echo "🔧 Nodes:"
	kubectl get nodes
	@echo ""
	@echo "🚀 Pods:"
	kubectl get pods -n web-services -o wide
	@echo ""
	@echo "🌐 Ingress:"
	kubectl get ingress -n web-services
	@echo ""
	@echo "📈 HPA:"
	kubectl get hpa -n web-services

# View logs (like docker-compose logs)
logs:
	kubectl logs -n web-services -l app=openwebui --tail=100 -f

# Quick restart (like docker-compose restart)
restart:
	kubectl rollout restart deployment/openwebui -n web-services
	kubectl rollout status deployment/openwebui -n web-services