PYTHON ?= python3

.PHONY: run test check up down
run:
	$(PYTHON) server.py

test:
	$(PYTHON) -m unittest discover -s tests -v
	node --test tests/model.test.mjs

check: test
	node --check static/app.js

up:
	docker compose up --build -d --wait

down:
	docker compose down
