# Makefile for OpenRouter Pricing Tracker

.PHONY: help install test run clean docker-build docker-up docker-down deploy logs

help:
	@echo "OpenRouter Pricing Tracker - Available commands:"
	@echo ""
	@echo "  make install       Install dependencies in virtual environment"
	@echo "  make test          Run tests (when implemented)"
	@echo "  make run           Run pricing tracker once"
	@echo "  make run-loop      Run continuous loop"
	@echo "  make clean         Remove generated files and cache"
	@echo ""
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-up     Start Docker container"
	@echo "  make docker-down   Stop Docker container"
	@echo "  make docker-logs   View Docker logs"
	@echo ""
	@echo "  make deploy        Deploy with systemd (requires sudo)"
	@echo "  make logs          View systemd logs"
	@echo ""

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

test:
	.venv/bin/pytest tests/ -v

run:
	.venv/bin/python -m app.main --once

run-loop:
	.venv/bin/python -m app.main

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	@echo "Cleaned up Python cache files"

docker-build:
	cd ops && docker-compose build

docker-up:
	cd ops && docker-compose up -d
	@echo "Container started. View logs with: make docker-logs"

docker-down:
	cd ops && docker-compose down

docker-logs:
	cd ops && docker-compose logs -f

deploy:
	@echo "Deploying with systemd..."
	cd ops && sudo bash deploy.sh

logs:
	sudo journalctl -u pricing-tracker.service -f

.DEFAULT_GOAL := help
