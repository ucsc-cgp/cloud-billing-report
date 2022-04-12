#!/bin/bash
set -eu

CONFIG=/root/reporting/config.json
IMAGE=ghcr.io/ucsc-cgp/cloud-billing-report:latest
REPORT_TYPE=$1
FAIL_LOG=/root/reporting/fail.log
AWS_PROFILE="FILL IN"
EMAIL_TMP_FILE=/tmp/${REPORT_TYPE}.eml
PERSONALIZED_EMAIL_DIR=/tmp/personalizedEmails

echo "Running container"
mkdir $PERSONALIZED_EMAIL_DIR

# Mount the config file, aws credentials, and a tmp directory into the docker container.
# The tmp directory will get populated with personalized emails.
(/usr/bin/docker pull ${IMAGE} > /dev/null 2>&1 && \
  /usr/local/bin/docker run \
  -v ${CONFIG}:/config.json:ro \
  -v ~/.aws/credentials:/root/.aws/credentials:ro \
  -e AWS_PROFILE=${AWS_PROFILE} \
  -v ~/.gcp/gcp-credentials.json:/gcp-credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/gcp-credentials.json \
  -v ${PERSONALIZED_EMAIL_DIR}/:/tmp/personalizedEmails/ \
  ${IMAGE} ${REPORT_TYPE})

sleep 5

for filename in ${PERSONALIZED_EMAIL_DIR}/*.eml; do
    # send the email file
    /usr/sbin/sendmail -t < $filename
    # remove the file
    rm -f $filename
    # try not to get throttled by gmail
    sleep 2
done

echo "Done"
