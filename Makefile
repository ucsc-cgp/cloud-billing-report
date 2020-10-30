SOURCE = report.py scripts/retry-failed-reports.py

.PHONY: pep8
pep8:
	flake8 --config .flake8/conf ${SOURCE}

.PHONY: format
format:
	docker run \
	    --rm \
	    --volume $$(pwd):/home/developer/cloud-billing-report \
	    --workdir /home/developer/cloud-billing-report rycus86/pycharm:2019.2.3 \
	    /opt/pycharm/bin/format.sh -r -settings .pycharm.style.xml -mask '*.py' ${SOURCE}

.PHONY: check_clean
check_clean:
	git diff --exit-code && git diff --cached --exit-code

.PHONY: test
test:
	python -m doctest ${SOURCE}
