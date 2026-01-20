.PHONY: help build up down restart logs logs-frontend logs-backend shell-frontend shell-backend \
        dev dev-fg dev-logs dev-logs-backend dev-logs-frontend dev-frontend dev-backend dev-backend-debug stop \
        install install-frontend install-backend install-uv clean clean-all prune status ps health rebuild lint lint-frontend

# Default target
.DEFAULT_GOAL := help

# Colors for help output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

#===============================================================================
# HELP
#===============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(GREEN)SMF Yield Defect Detection - Makefile Commands$(RESET)"
	@echo ""
	@echo "$(CYAN)Docker Commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(build|up|down|restart|logs|shell|clean|prune|status|ps|health|rebuild)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Local Development:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | grep -E '(dev|stop|install|lint|test)' | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""

#===============================================================================
# DOCKER - MAIN COMMANDS
#===============================================================================

build: ## Build and start all containers (one command to run everything)
	docker-compose up --build -d
	@echo ""
	@echo "$(GREEN)Services are starting...$(RESET)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo ""
	@echo "Run 'make logs' to view logs or 'make status' to check container status"

up: ## Start all containers (without rebuilding)
	docker-compose up -d
	@echo ""
	@echo "$(GREEN)Services started$(RESET)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"

down: ## Stop and remove all containers
	docker-compose down

restart: ## Restart all containers
	docker-compose restart

rebuild: ## Force rebuild all containers from scratch (no cache)
	docker-compose build --no-cache
	docker-compose up -d

#===============================================================================
# DOCKER - LOGS & DEBUGGING
#===============================================================================

logs: ## View logs from all containers (follow mode)
	docker-compose logs -f

logs-frontend: ## View frontend container logs
	docker-compose logs -f my-agentic-workflow-front

logs-backend: ## View backend container logs
	docker-compose logs -f my-agentic-workflow-back

logs-tail: ## View last 100 lines of logs from all containers
	docker-compose logs --tail=100

shell-frontend: ## Open shell in frontend container
	docker exec -it my-agentic-workflow-front-container /bin/sh

shell-backend: ## Open shell in backend container
	docker exec -it my-agentic-workflow-back-container /bin/bash

#===============================================================================
# DOCKER - STATUS & HEALTH
#===============================================================================

status: ## Show status of all containers
	@echo "$(CYAN)Container Status:$(RESET)"
	@docker-compose ps
	@echo ""
	@echo "$(CYAN)Resource Usage:$(RESET)"
	@docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "No running containers"

ps: ## List all running containers
	docker-compose ps

health: ## Check health of services
	@echo "$(CYAN)Checking service health...$(RESET)"
	@echo ""
	@echo "Frontend (http://localhost:3000):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:3000 2>/dev/null || echo "  Status: Not reachable"
	@echo ""
	@echo "Backend (http://localhost:8000):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8000 2>/dev/null || echo "  Status: Not reachable"
	@echo ""
	@echo "Backend API Docs (http://localhost:8000/docs):"
	@curl -s -o /dev/null -w "  Status: %{http_code}\n" http://localhost:8000/docs 2>/dev/null || echo "  Status: Not reachable"

#===============================================================================
# DOCKER - CLEANUP
#===============================================================================

clean: ## Stop containers and remove images/volumes for this project
	docker-compose down --rmi all -v

clean-all: ## Full cleanup: remove all containers, images, volumes, and networks
	docker-compose down --rmi all -v --remove-orphans
	@echo "$(YELLOW)Removing dangling images...$(RESET)"
	docker image prune -f

prune: ## Remove all unused Docker resources (system-wide)
	@echo "$(YELLOW)Warning: This will remove all unused Docker resources system-wide$(RESET)"
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] && docker system prune -af --volumes || echo "Cancelled"

#===============================================================================
# LOCAL DEVELOPMENT - INSTALL DEPENDENCIES
#===============================================================================

install: install-frontend install-backend ## Install all dependencies locally

install-frontend: ## Install frontend dependencies
	cd frontend && npm install --legacy-peer-deps

install-backend: ## Install backend dependencies using UV
	cd backend && uv sync

install-uv: ## Install UV package manager (if not installed)
	@command -v uv >/dev/null 2>&1 || (echo "Installing UV..." && curl -LsSf https://astral.sh/uv/install.sh | sh)

#===============================================================================
# LOCAL DEVELOPMENT - RUN SERVICES
#===============================================================================

dev: stop ## Run frontend and backend in background
	@mkdir -p .logs
	@echo "$(GREEN)Starting services in background...$(RESET)"
	@cd backend && nohup uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload > ../.logs/backend.log 2>&1 &
	@cd frontend && nohup npm run dev > ../.logs/frontend.log 2>&1 &
	@sleep 2
	@echo ""
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"
	@echo ""
	@echo "$(CYAN)Commands:$(RESET)"
	@echo "  make stop      - Stop all services"
	@echo "  make dev-logs  - Tail logs"
	@echo ""

dev-logs: ## Tail logs from background services
	@tail -f .logs/backend.log .logs/frontend.log

dev-logs-backend: ## Tail backend logs only
	@tail -f .logs/backend.log

dev-logs-frontend: ## Tail frontend logs only
	@tail -f .logs/frontend.log

dev-fg: stop ## Run frontend and backend in foreground (blocking)
	@echo ""
	@echo "$(GREEN)Starting services (foreground)...$(RESET)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo ""
	@echo "$(YELLOW)Press Ctrl+C to stop$(RESET)"
	@echo ""
	@trap 'kill 0' INT TERM; \
	(cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload) & \
	(cd frontend && npm run dev) & \
	wait

stop: ## Stop all running services
	@-lsof -ti:3000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@echo "$(GREEN)Services stopped$(RESET)"

dev-frontend: ## Run frontend locally in development mode
	cd frontend && npm run dev

dev-backend: ## Run backend locally with hot reload
	cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

dev-backend-debug: ## Run backend with debug logging
	cd backend && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

#===============================================================================
# LOCAL DEVELOPMENT - LINTING & TESTING
#===============================================================================

lint: lint-frontend ## Run linters

lint-frontend: ## Run frontend linter
	cd frontend && npm run lint

#===============================================================================
# LEGACY COMMANDS (Poetry - deprecated, use UV instead)
#===============================================================================

install-poetry: ## [DEPRECATED] Install Poetry (use install-uv instead)
	@echo "$(YELLOW)Warning: Backend now uses UV, not Poetry$(RESET)"
	brew install pipx
	pipx ensurepath
	pipx install poetry==1.8.4

poetry-install: ## [DEPRECATED] Install backend deps with Poetry
	@echo "$(YELLOW)Warning: Backend now uses UV, not Poetry$(RESET)"
	cd backend && poetry install --no-interaction -v --no-cache --no-root
