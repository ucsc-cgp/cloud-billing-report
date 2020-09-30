PERLFILES = aws/report_aws_spending gcp/report_gcp_spending

lint:
	docker run -v ${PWD}:/tmp/workspace ghcr.io/natanlao/critic:latest ${PERLFILES}
	perltidy ${PERLFILES}
