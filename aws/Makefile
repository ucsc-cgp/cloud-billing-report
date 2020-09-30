include ../common.mk

.PHONY: build
build:
	docker build -t report_aws .

report.eml: build
	docker run \
		-v $(shell pwd)/report.eml:/root/aws-reporting/report.html \
		report_aws ${REPORT_DATE}
