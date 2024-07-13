###############################################################################
### make Configuration
###
### This file defines configuration used in the Makefile.
### You may add and/or override these values with your own custom configuration
### in `config.local.mk`.
###
###############################################################################

# List of tools that must be installed.
# A simple check to determine the tool is available. No version check, etc.
define REQUIRED_SOFTWARE
docker \
git
endef