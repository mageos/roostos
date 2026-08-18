# RoostOS Build System Makefile

REGISTRY ?= localhost:5000

.PHONY: all images push deb test test-ui install-ui-deps clean help

all: images deb

images:
	@echo "============================================="
	@echo "Building RoostOS Plugin Docker Images"
	@echo "============================================="
	docker build -t roostos-dns-technitium:latest -f roostos-dns-technitium/Dockerfile .

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
	@NEW_VERSION=$$(awk -F= '/^PACKAGE_VERSION=/ {split($$2, a, "."); print a[1]"."a[2]"."(a[3]+1)}' scripts/build-deb.sh) && \
	sed -i "s/^PACKAGE_VERSION=.*/PACKAGE_VERSION=$$NEW_VERSION/" scripts/build-deb.sh && \
	echo "PACKAGE_VERSION auto-incremented to $$NEW_VERSION"

deb: bump-version
	@echo "============================================="
	@echo "Building RoostOS Debian Packages"
	@echo "============================================="
	bash scripts/build-all-debs.sh

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
	.venv/bin/pytest roostos-engine/tests/ roostos-web/tests/unit/

clean:
	@echo "Cleaning build artifacts..."
	rm -rf build-deb-tmp
	rm -f roostos_*.deb
	rm -f *.tar

help:
	@echo "Available targets:"
	@echo "  all     - Build all Docker images and the Debian package (default)"
	@echo "  images  - Build the roostos-dns-technitium docker image"
	@echo "  push    - Tag and push D-Bus sidecar and base Technitium DNS to registry"
	@echo "  deb     - Compile the Debian installation package"
	@echo "  test    - Run python and javascript unit tests"
	@echo "  test-ui - Run frontend javascript unit tests"
	@echo "  clean   - Remove temporary build folders, generated debs and tars"
