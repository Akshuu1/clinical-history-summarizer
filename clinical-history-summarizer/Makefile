.PHONY: test run-backend run-frontend generate-cases setup

# Run the evaluation scripts against our test cases
test:
	.venv/bin/python scripts/evaluate.py

# Generate 110 synthetic test cases using OpenRouter/LLM
generate-cases:
	.venv/bin/python scripts/generate_110_cases.py --start 16 --end 110

# Run the FastAPI backend server
run-backend:
	.venv/bin/uvicorn app.main:app --reload --port 8000

# Run the Next.js frontend UI
run-frontend:
	cd frontend && npm run dev -- --port 3000

# Run both backend and frontend concurrently (requires 'make' and a Unix shell)
run-all:
	make run-backend & make run-frontend & wait

# Install backend dependencies
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	cd frontend && npm install
