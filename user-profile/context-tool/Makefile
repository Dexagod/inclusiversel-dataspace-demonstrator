PYTHON ?= python3

.PHONY: run test check golden up down

run:             ## local, without Docker: http://127.0.0.1:8095
	$(PYTHON) server.py

test:
	$(PYTHON) -m unittest discover -s tests -v

check: test
	$(PYTHON) -m json.tool crosswalk.json > /dev/null

# Regenerate the expected outputs after an intended change; review the diff before committing.
golden:
	for f in examples/*.json; do $(PYTHON) generate.py $$f > $${f%.json}.md; done

up:              ## Docker service on 127.0.0.1:8095 (PROFILE_BIND in .env changes the address)
	docker compose up --build -d --wait

down:
	docker compose down
