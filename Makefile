define HELP_TEXT
Usage:
	make help               show this message
	make specs              produces all specs
	make list-specs         list specs to be made (will trigger scrape-base if not done already)
	make spec NAME=name     produces all versions of `name` spec (eg: localidades ou malhas).

	make install            install dependencies for development
	make lab                opens jupyter lab in current virtualenv

	make validate           runs lint and typecheck in src/*
	make lint               runs lint
	make typecheck          runs typecheck
endef
export HELP_TEXT


SRC := src
PY := poetry run python
PYMAIN := $(PY) -m $(SRC)

SPECS_BASE := specs-base.yaml
SPECS_DIR := specs
HTMLS_DIR := raw_htmls
HAND_FIXES := hand-fixes.yaml

# helper text procedure, filters by containing string
# eg: $(call CONTAINS,foo,foo.yaml bar.yaml foo.html)
# -> foo.yaml foo.html
CONTAINS = $(foreach element,\
	$(2),\
	$(if $(findstring $(1),$(element)),\
		$(element),\
		\
	)\
)


all: help
.PHONY: all


.PHONY: help
help:
	@echo "$${HELP_TEXT}"


.PHONY: specs
specs:
	$(MAKE) $(shell $(MAKE) list-specs)


# USAGE: make spec NAME=foo
.PHONY: spec
spec:
	$(MAKE) $(strip $(call CONTAINS,$(NAME),$(shell $(MAKE) list-specs)))


.PHONY: list-specs
list-specs: $(SPECS_BASE)
	@echo $(foreach slug_version,\
		$(shell $(PYMAIN) $@ --specs-base $^),\
		$(SPECS_DIR)/$(slug_version).yaml\
	)


# executes $(1) and catches stderr to a temporary file
# if error do occur (ie, if $(1) returns non 0 code):
#   removes target file
#   shows the stderr saved
#   copy it to a logfile in current directory
define handle-fail
@TEMP_LOG_FILE=$(shell mktemp) \
	; LOG_FILE="$(@D)!$(@F).log" \
	&& $(1) \
		2> $${TEMP_LOG_FILE} \
	|| (cp $${TEMP_LOG_FILE} $${LOG_FILE} \
	; rm $@ \
	; cat $${LOG_FILE} \
	; echo \
	; echo \
	; echo '*****************' \
	; echo Check the log file $(CURDIR)/$${LOG_FILE} \
	; exit 1)
endef


.PRECIOUS: $(SPECS_DIR)/%.yaml
$(SPECS_DIR)/%.yaml: $(HTMLS_DIR)/%.html $(SPECS_BASE)
	mkdir -p $(@D)
	$(call handle-fail,$(PYMAIN) parse \
		--slug $* \
		--html $< \
		--hand-fixes $(HAND_FIXES) \
		--specs-base $(SPECS_BASE) \
		1> $@)


.PRECIOUS: $(HTMLS_DIR)/%.html
$(HTMLS_DIR)/%.html: $(SPECS_BASE)
	mkdir -p $(@D)
	$(call handle-fail,$(PYMAIN) fetch \
		--slug $* \
		--specs-base $(SPECS_BASE) \
		1> $@)


# .PRECIOUS: $(SPECS_DIR)/%.yaml
# $(SPECS_DIR)/%.yaml: $(HTMLS_DIR)/%.html $(SPECS_BASE)
# 	mkdir -p $(@D)
# 	$(PYMAIN) parse \
# 		--slug $* \
# 		--html $< \
# 		--hand-fixes $(HAND_FIXES) \
# 		--specs-base $(SPECS_BASE) \
# 		1> $@ \
# 		2> $${TEMP_FILE}


# meant to scrape the index page, and build the info to the specs to be scraped
$(SPECS_BASE):
	$(PYMAIN) $(basename $@) > $@


.PHONY: clean_logs
clean_logs:
	rm -f *.log

################### dev targets below ##################

.PHONY: install
install:
	poetry install


.PHONY: lab
lab:
	poetry run jupyter lab .


.PHONY: validate
validate:
	$(MAKE) lint && \
		$(MAKE) typecheck


.PHONY: lint
lint:
	@echo "\n\n" ======== $@ ========= "\n\n"
	poetry run flake8


.PHONY: typecheck
typecheck:
	@echo "\n\n" ======== $@ ========= "\n\n"
	poetry run mypy $(SRC)
