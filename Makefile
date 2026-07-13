.PHONY: paperclip-clone paperclip-start paperclip-stop paperclip-logs paperclip-status hermes-install hermes-verify hermes-test-sdq hermes-path hermes-version hermes-gateway-build hermes-gateway-start hermes-gateway-stop hermes-gateway-logs hermes-gateway-health hermes-gateway-verify sandbox bootstrap-local verify-local bootstrap-oracle verify-oracle backup restore diagnostics recovery-check

paperclip-clone:
	./platform/paperclip/scripts/clone-or-update.sh

paperclip-start:
	./platform/paperclip/scripts/start.sh

paperclip-stop:
	./platform/paperclip/scripts/stop.sh

paperclip-logs:
	./platform/paperclip/scripts/logs.sh

paperclip-status:
	./platform/paperclip/scripts/verify.sh

hermes-install:
	./runtime/hermes/install-local.sh

hermes-verify:
	./runtime/hermes/verify-local.sh

hermes-test-sdq:
	./runtime/hermes/google-ads-agent/scripts/test-performance-summary.sh $(TENANT)

hermes-path:
	@printf '%s\n' "$(CURDIR)/runtime/hermes/hermes-local.sh"

hermes-version:
	./runtime/hermes/hermes-local.sh --version

hermes-gateway-build:
	./runtime/hermes/gateway/scripts/build.sh

hermes-gateway-start:
	./runtime/hermes/gateway/scripts/start.sh

hermes-gateway-stop:
	./runtime/hermes/gateway/scripts/stop.sh

hermes-gateway-logs:
	./runtime/hermes/gateway/scripts/logs.sh

hermes-gateway-health:
	./runtime/hermes/gateway/scripts/health.sh

hermes-gateway-verify:
	./runtime/hermes/gateway/scripts/verify.sh

sandbox:
	docker compose up -d --build
	./sandbox/sdq-labs-growth/scripts/run-demo-flow.sh

bootstrap-local:
	./recovery/scripts/bootstrap-local.sh

verify-local:
	./recovery/scripts/verify-local.sh

bootstrap-oracle:
	./recovery/scripts/bootstrap-oracle.sh

verify-oracle:
	./recovery/scripts/verify-oracle.sh

backup:
	./recovery/scripts/backup.sh

restore:
	./recovery/scripts/restore.sh $(BACKUP)

diagnostics:
	./recovery/scripts/collect-diagnostics.sh

recovery-check: verify-local
