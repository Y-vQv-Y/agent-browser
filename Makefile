.PHONY: install dev test test-unit test-integration test-cov lint lint-fix type-check clean build docker run-cli run-web help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	python -m pip install --upgrade pip setuptools wheel
	pip install greenlet --only-binary=greenlet || true
	pip install -e .
	playwright install chromium

dev: ## Install with dev dependencies
	python -m pip install --upgrade pip setuptools wheel
	pip install greenlet --only-binary=greenlet || true
	pip install -e ".[dev]"
	playwright install chromium

test: ## Run all tests (unit + integration, no browser)
	pytest tests/ -v --tb=short -k "not browser"

test-unit: ## Run unit tests only
	pytest tests/ -v --tb=short -k "not browser and not integration"

test-integration: ## Run integration tests
	pytest tests/test_integration.py -v --tb=short

test-cov: ## Run tests with coverage
	pytest tests/ -v --tb=short --cov=agent_browser --cov-report=html --cov-report=term -k "not browser"

lint: ## Run linter
	ruff check src/ tests/

lint-fix: ## Fix linting issues
	ruff check --fix src/ tests/

type-check: ## Run type checker
	mypy src/agent_browser/ --ignore-missing-imports

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov coverage.xml .mypy_cache .ruff_cache

build: ## Build package
	python -m pip install --upgrade pip setuptools wheel
	pip install build
	python -m build

docker: ## Build Docker image
	docker build -t agent-browser:latest .

run-cli: ## Run CLI interactive mode
	ab run

run-web: ## Start Web GUI
	ab web

doctor: ## Check system dependencies
	ab doctor

configure: ## Configure the agent
	ab configure

chromium-install: ## Install CloakBrowser Chromium
	ab chromium install

chromium-info: ## Show CloakBrowser Chromium info
	ab chromium info

profiles: ## List session profiles
	ab profiles list
