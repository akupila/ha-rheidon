# Override on the command line or in .envrc, e.g. HA_HOST=root@192.168.1.10
HA_HOST ?= root@homeassistant.local
HA_CONFIG ?= /config

# Tests need Python 3.14, e.g. `nix shell nixpkgs#python314 -c make test`.
PYTHON ?= python3.14

COMPONENT := rheidon
DEST := $(HA_CONFIG)/custom_components/$(COMPONENT)

.PHONY: install restart check test

# Copy the integration to Home Assistant over SSH, replacing any previous copy.
install: check
	COPYFILE_DISABLE=1 tar -C custom_components --exclude __pycache__ --no-xattrs --no-mac-metadata -cf - $(COMPONENT) \
		| ssh $(HA_HOST) 'rm -rf $(DEST) && mkdir -p $(HA_CONFIG)/custom_components && tar -C $(HA_CONFIG)/custom_components -xf -'
	@echo "Installed to $(HA_HOST):$(DEST). Restart Home Assistant to load it (make restart)."

# Restart Home Assistant Core. Needs the `ha` CLI, available in the Terminal & SSH add-on.
restart:
	ssh $(HA_HOST) 'ha core restart'

# Syntax-check the integration.
check:
	python3 -m py_compile custom_components/$(COMPONENT)/*.py
	find custom_components -name __pycache__ -prune -exec rm -rf {} +

# Run the tests in a local virtualenv (created on first run).
test: .venv/.installed
	.venv/bin/pytest $(PYTEST_ARGS)

.venv/.installed: requirements_test.txt
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -q -r requirements_test.txt
	touch $@
