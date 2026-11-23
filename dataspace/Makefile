PY := uv run --python 3.12
COMPONENTS := catalog connector vochub

.PHONY: calls up up-catalog up-vochub up-connector down check test logs clean

up:            ## start the stack
	@test -f .env || cp .env.example .env
	docker compose up --build -d --wait

up-catalog:    ## only the catalog (broker)
	docker compose up --build -d --wait catalog

up-vochub:     ## only the vocabulary hub and its vector store
	docker compose up --build -d --wait vochub vochub-vectors

up-connector:  ## only the connector, using CATALOG_URL, VOCHUB_URL and SOURCE_URL_MAP from .env
	@test -f .env || cp .env.example .env
	docker compose up --build -d --wait --no-deps connector

down:
	docker compose down

test:          ## unit and contract tests of every component, offline
	@for c in $(COMPONENTS); do echo "== $$c"; (cd $$c && $(PY) --with-requirements requirements.txt --with pytest pytest -q) || exit 1; done

check: test    ## the gate: tests plus a compose build
	docker compose config -q
	docker compose build

calls:         ## summary of the connector's logged tool calls (needs CALL_LOG=1 in .env); SINCE=30m limits it
	docker compose logs --no-log-prefix $(if $(SINCE),--since $(SINCE),) connector | python3 connector/calls.py

logs:
	docker compose logs -f

clean:         ## stop and delete all volumes (catalog registrations and vectors)
	docker compose down -v
