# Everyday commands for the whole demonstrator: data space, sources and viewer.
# The content set is public (what may be published) or full (also private sources and licence-restricted documents;
# local use and closed demos). The last one chosen is remembered in .content-mode; MODE=public|full overrides it.

MODE ?= $(shell cat .content-mode 2>/dev/null || echo public)
SEED := cd sources && uv run --python 3.12 --with httpx --with pyyaml python seed.py

.PHONY: help start start-public start-full public full restart stop update reset-knowledge reset-catalog reset \
        status calls logs test

help:            ## list the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | expand -t 18
	@echo "\ncontent set now: $(MODE)"

start:           ## build and start everything, then load the content set (MODE=public|full, default the last one)
	$(MAKE) -C dataspace up
	$(MAKE) -C sources up
	$(MAKE) -C viewer up
	$(MAKE) $(MODE)

start-public:    ## start, with only what may be published (for a published server)
	$(MAKE) start MODE=public

start-full:      ## start, with everything (local use, closed demos)
	$(MAKE) start MODE=full

public:          ## switch the running data space to the public set (removes private sources and restricted documents)
	@echo public > .content-mode
	$(SEED) public

full:            ## switch the running data space to the full set
	@echo full > .content-mode
	$(SEED) full

restart:         ## restart every container; registrations, documents and caches stay
	cd dataspace && docker compose restart
	cd sources && docker compose restart
	cd viewer && docker compose restart

stop:            ## stop everything (data stays on the volumes; start brings it back)
	$(MAKE) -C viewer down
	$(MAKE) -C sources down
	$(MAKE) -C dataspace down

update:          ## git pull, rebuild what changed, and load the content set again
	git pull
	$(MAKE) start

reset-knowledge: ## empty the vocabulary hub and load the documents of the content set again
	$(SEED) clear-knowledge
	$(MAKE) $(MODE)

reset-catalog:   ## empty the catalog and register the sources of the content set again
	$(SEED) clear-catalog
	$(MAKE) $(MODE)

reset:           ## both resets
	$(SEED) clear-catalog
	$(SEED) clear-knowledge
	$(MAKE) $(MODE)

status:          ## what is running and what it holds
	@$(SEED) status; echo "content set:    $(MODE) (last chosen)"

calls:           ## the connector's logged tool calls (needs CALL_LOG=1 in dataspace/.env); SINCE=30m limits them
	$(MAKE) -C dataspace calls SINCE=$(SINCE)

logs:            ## follow the logs of the data space
	$(MAKE) -C dataspace logs

test:            ## offline tests of every component
	$(MAKE) -C dataspace test
	$(MAKE) -C sources test
	$(MAKE) -C viewer test
