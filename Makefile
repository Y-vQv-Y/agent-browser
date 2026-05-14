.PHONY: install dev test lint type-check clean build docker run-cli run-web help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .
	playwright install chromium

dev: ## Install with dev dependencies
	pip install -e ".[dev]"
	playwright install chromium

test: ## Run all tests
	pytest tests/test_config.py tests/test_llm.py tests/test_memory.py tests/test_scheduler.py tests/test_stealth.py tests/test_humanize.py tests/test_captcha.py tests/test_agent.py tests/test_cli.py tests/test_web.py -v --tb=short

test-unit: ## Run unit tests only (no browser needed)
	pytest tests/test_config.py tests/test_llm.py tests/test_memory.py tests/test_scheduler.py tests/test_stealth.py tests/test_humanize.py tests/test_captcha.py tests/test_agent.py tests/test_cli.py tests/test_web.py -v --tb=short

test-cov: ## Run tests with coverage
	pytest tests/ -v --tb=short --cov=agent_browser --cov-report=html --cov-report=term

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
	python -m build

docker: ## Build Docker image
	docker build -t agent-browser:latest .

run-cli: ## Run CLI interactive mode
	python -m agent_browser run

run-web: ## Start Web GUI
	python -m agent_browser web

doctor: ## Check system dependencies
	python -m agent_browser doctor

configure: ## Configure the agent
	python -m agent_browser configure
