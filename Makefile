# RoostOS Build System Makefile

REGISTRY ?= localhost:5000
VERSION ?= $(shell cat VERSION 2>/dev/null | tr -d '[:space:]' || echo "0.1.0")

.PHONY: all images push deb arch pkgs bump-version test test-ui install-ui-deps clean help

all: images pkgs

images:
	@echo "============================================="
	@echo "Building RoostOS Plugin Docker Images"
	@echo "============================================="
	docker build -t roostos-dns-technitium:latest -f roostos-dns-technitium/Dockerfile .
	docker build -t roostos-identity-samba:latest -f roostos-identity-samba/Dockerfile .

push: images
	@echo "============================================="
	@echo "Tagging and Pushing Images to Registry: $(REGISTRY)"
	@echo "============================================="
	# Tag and push D-Bus bridge sidecar
	docker tag roostos-dns-technitium:latest $(REGISTRY)/roostos-dns-technitium:latest
	docker push $(REGISTRY)/roostos-dns-technitium:latest
	# Pull, tag, and push Technitium base image
	docker pull technitium/dns-server:latest
	docker tag technitium/dns-server:latest $(REGISTRY)/technitium/dns-server:latest
	docker push $(REGISTRY)/technitium/dns-server:latest

bump-version:
	@OLD_VER=$$(cat VERSION 2>/dev/null | tr -d '[:space:]' || echo "0.1.0") && \
	NEW_VER=$$(echo "$$OLD_VER" | awk '{split($$0, a, "."); print a[1]"."a[2]"."(a[3]+1)}') && \
	echo "$$NEW_VER" > VERSION && \
	sed -i "s/^pkgver=.*/pkgver=$$NEW_VER/" packaging/arch/PKGBUILD 2>/dev/null || true && \
	echo "RoostOS Version bumped: $$OLD_VER -> $$NEW_VER"

deb:
	@echo "============================================="
	@echo "Building RoostOS Debian Packages (v$(VERSION))"
	@echo "============================================="
	bash packaging/debian/build-debs.sh

arch:
	@echo "============================================="
	@echo "Building RoostOS Arch Linux Packages (v$(VERSION))"
	@echo "============================================="
	bash packaging/arch/build-arch.sh

pkgs: deb arch

install-ui-deps:
	npm install --prefix roostos-ui

dev:
	@echo "============================================="
	@echo "Starting RoostOS Full-Stack Dev Sandbox"
	@echo "============================================="
	python3 scripts/run_dev.py

dev-ui:
	@echo "============================================="
	@echo "Starting RoostOS Mock UI Dev Server on :3000"
	@echo "============================================="
	npm run dev --prefix roostos-ui

test-ui:
	@echo "============================================="
	@echo "Running Frontend JavaScript Unit Tests"
	@echo "============================================="
	npm test --prefix roostos-ui

test: test-ui
	@echo "============================================="
	@echo "Running Backend Python Unit Tests"
	@echo "============================================="
	.venv/bin/pytest tests/harness/ tests/automation/test_scenarios.py roostos-engine/tests/ roostos-web/tests/unit/

test-harness:
	@echo "============================================="
	@echo "Running Containerized Multi-Node Test Harness"
	@echo "============================================="
	python3 scripts/run_test_harness.py

test-harness-up:
	@echo "============================================="
	@echo "Starting Interactive Test Harness (Web: :8080)"
	@echo "============================================="
	python3 scripts/run_test_harness.py --interactive

test-harness-down:
	@echo "============================================="
	@echo "Tearing Down Test Harness Containers"
	@echo "============================================="
	python3 scripts/run_test_harness.py --down

test-harness-logs:
	docker compose -f test-harness/docker-compose.yml logs -f

test-harness-scenario:
	@echo "============================================="
	@echo "Running Test Harness with Scenario: $(SCENARIO)"
	@echo "============================================="
	python3 scripts/run_test_harness.py --scenario $(SCENARIO)

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build-deb-tmp build-arch-tmp
	rm -rf test-harness/staged-config
	rm -rf dist
	rm -f roostos_*.deb *.pkg.tar* *.tar

help:
	@echo "Available targets:"
	@echo "  all                  - Build all Docker images, Debian, and Arch packages (default)"
	@echo "  images               - Build the roostos-dns-technitium docker image"
	@echo "  push                 - Tag and push D-Bus sidecar and base Technitium DNS to registry"
	@echo "  deb                  - Compile Debian (.deb) packages"
	@echo "  arch                 - Compile Arch Linux (.pkg.tar.zst) packages"
	@echo "  pkgs                 - Compile both Debian and Arch Linux packages"
	@echo "  bump-version         - Increment patch version in VERSION and sync PKGBUILD"
	@echo "  test                 - Run python and javascript unit tests"
	@echo "  test-ui              - Run frontend javascript unit tests"
	@echo "  test-harness         - Run containerized multi-node automation test suite"
	@echo "  test-harness-up      - Start container network for interactive Web UI testing on :8080"
	@echo "  test-harness-down    - Teardown test harness containers and networks"
	@echo "  test-harness-scenario - Run test harness with SCENARIO=<name> (e.g. multi-wan)"
	@echo "  clean                - Remove temporary build folders, generated debs and tars"

