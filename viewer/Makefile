PYTHON ?= python3

.PHONY: run test check up down
run:
	$(PYTHON) server.py

test:
	$(PYTHON) -m unittest discover -s tests -v
	node --test tests/*.test.mjs

check: test
	node --check static/app.js

up:
	docker compose up --build -d --wait

down:
	docker compose down

.PHONY: logs demo-up
logs:
	$(PYTHON) collect_logs.py

demo-up:
	mkdir -p .logs
	docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d --wait
