include ../common.mk

.PHONY: build
build:
	docker build -t report_aws .

report.eml: build
	docker run \
		-v $(shell pwd)/config.pl:/root/aws-reporting/config.pl:ro \
		report_aws ${REPORT_DATE} > report.eml
