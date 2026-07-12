.PHONY: paperclip-clone paperclip-start paperclip-stop paperclip-logs paperclip-status hermes-install hermes-verify hermes-test-sdq bootstrap-local verify-local bootstrap-oracle verify-oracle backup restore diagnostics recovery-check

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
