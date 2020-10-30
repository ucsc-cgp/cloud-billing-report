#!/bin/bash
set -euf

CONFIG=/root/reporting/config.json
IMAGE=ghcr.io/ucsc-cgp/cloud-billing-report:latest
REPORT_TYPE=$1
FAIL_LOG=/root/reporting/fail.log
GOOGLE_ACCOUNT_CREDENTIALS=/root/reporting/gcp-credentials.json

EMAIL_TMPFILE=/tmp/${REPORT_TYPE}.eml
# GNU coreutils
REPORT_DATE=$(date -d 'today - 1 d' +%Y-%m-%d)

(/usr/bin/docker run \
    -v ${CONFIG}:/config.json:ro \
    -v ${GOOGLE_ACCOUNT_CREDENTIALS}:/gcp-credentials.json:ro \
    ${IMAGE} ${REPORT_TYPE} ${REPORT_DATE} \
    > ${EMAIL_TMPFILE} \
&& /usr/sbin/sendmail -t < ${EMAIL_TMPFILE}) \
|| echo "${REPORT_TYPE},${REPORT_DATE}" >> ${FAIL_LOG}