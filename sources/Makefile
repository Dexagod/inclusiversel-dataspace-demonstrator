PY := uv run --python 3.12
TESTED := iedereenoveral pictoaccess be-transit

.PHONY: up down test register knowledge e2e

up:            ## start the source proxies (the data space must be up: make -C ../dataspace up)
	docker compose up --build -d --wait

down:
	docker compose down

test:          ## offline unit tests of the proxies
	@for c in $(TESTED); do echo "== $$c"; (cd $$c && $(PY) --with-requirements requirements.txt --with pytest pytest -q) || exit 1; done

register:      ## register every */registration.json in the catalog over HTTP
	$(PY) --with httpx --with pyyaml python seed.py register

knowledge:     ## ingest domain-knowledge.yaml into the vocabulary hub over HTTP (needs internet)
	$(PY) --with httpx --with pyyaml python seed.py knowledge

e2e:           ## data space + sources end to end (after up and register)
	$(PY) --with "mcp>=2.3,<3" --with httpx python tests/e2e.py
