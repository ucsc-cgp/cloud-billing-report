include ../common.mk

REPORT_DATE ?= $(shell gdate -d 'today - 3 days' '+%Y-%m-%d')

.PHONY: build
build:
	docker build -t report_gcp .

report.eml: build
	docker run \
		-v ~/.config/gcloud/:/root/.config/gcloud/:ro \
		-v $(shell pwd)/config.pl:/root/gcp-reporting/config.pl:ro \
		report_gcp ${REPORT_DATE} > report.eml

