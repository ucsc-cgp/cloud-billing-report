ADMIN_ADDRESS := $(shell perl -e 'my $$config = do "${CURDIR}/config.pl"; print $$config->{report}{from}')

.PHONY: send
send: report.eml
	# Confirm that report is only being sent to tester
	grep -Fxq "To: ${ADMIN_ADDRESS}" report.eml
	sendmail -t < ${CURDIR}/report.eml
	rm ${CURDIR}/report.eml

# Given a dirty working tree, verify that the report generated with
# uncomitted changes is the same as the report generated from the last
# commit. Brittle.
.PHONY: assert_semantically_neutral
assert_semantically_neutral:
	${MAKE} -f ${CURDIR}/Makefile report.eml
	mv ${CURDIR}/report.eml ${CURDIR}/report-dirty.eml
	git stash
	${MAKE} -f ${CURDIR}/Makefile report.eml
	mv ${CURDIR}/report.eml ${CURDIR}/report-clean.eml
	git stash pop
	diff ${CURDIR}/report-dirty.eml ${CURDIR}/report-clean.eml
	rm ${CURDIR}/report-dirty.eml ${CURDIR}/report-clean.eml
