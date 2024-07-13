###############################################################################
### Loaded Configuration
### Load configuration from external files. Configuration variables defined in
### later files have precedent and will overwrite those defined in previous
### files. The -include directive ensures that no error is thrown if a file is
### not found, which is the case if config.local.mk does not exist.
###############################################################################
-include config.mk
-include config.local.mk


.PHONY: init
init: dependencies start-project


###############################################################################
### Verify prerequisite software is installed.
###############################################################################
is-not-installed=! (command -v $(1) >/dev/null)

define dependency-template
dependency-$(1):
	@if ( $(call is-not-installed,$(1)) ); \
	then \
	  echo "Dependency" $(1) " not found in path." \
	  && exit 102; \
	else \
	  echo "Dependency" $(1) "found."; \
	fi;
endef
$(foreach pkg,$(REQUIRED_SOFTWARE),$(eval $(call dependency-template,$(pkg))))

.PHONY: dependencies
dependencies: $(foreach pkg,$(REQUIRED_SOFTWARE),dependency-$(pkg))



###############################################################################
### Localstack start stop
###############################################################################

.PHONY: start-project
start-project: stop-project
	docker compose -f "docker/docker-compose.yml" up -d

.PHONY: stop-project
stop-project:
	docker compose -f "docker/docker-compose.yml" down


###############################################################################
### Install dev dependecies
###############################################################################

.PHONY: install-dev
install-dev:
	docker exec -it -w /apache-iceberge-s3/tools docker-app-1 pip install  -e .



.PHONY: cleanup-tf-states
cleanup-tf-states:
	find . -wholename "**/.terraform" -exec rm -rf "{}" \; \
	&& find . -wholename "*.terraform.lock.hcl" -exec rm -rf "{}" \; \
	&& find . -wholename "*.plan" -exec rm -rf "{}" \;  \
	&& find . -wholename "*.tfstate" -exec rm -rf "{}" \; \
	&& find . -wholename "*.tfstate.backup" -exec rm -rf "{}" \;



###############################################################################
### setup iceberge tables and other assets s3
###############################################################################




