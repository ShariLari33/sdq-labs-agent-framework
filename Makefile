.PHONY: paperclip-clone paperclip-start paperclip-stop paperclip-logs paperclip-status

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
