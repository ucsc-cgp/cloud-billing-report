# cloud-billing-report

Summarizes AWS and GCP billing data into an email report. Originally written
by Erich Weiler.

This repository was previously named ucsc-cgp/aws-billing-report. It was
renamed to ucsc-cgp/cloud-billing-report.

## Getting started

### Cloud setup

Billing data is presented using

* the [S3 Cost and Usage Report][s3] feature for AWS, and

* the [GCS Cloud Billing][gcs] feature for GCP.

Credentials configured in `config.json` must be authorized for access to
billing data generated these features.

  [s3]: https://docs.aws.amazon.com/cur/latest/userguide/cur-s3.html
  [gcs]: https://cloud.google.com/billing/docs/how-to/export-data-file

### Generating reports

You'll need Python 3.x. I've only tested this using Python 3.8.6.

First, populate `config.json` and install requirements:

```console
$ cp config.json.example config.json  # and populate it
$ python -m venv venv
$ source venv/bin/activate
$ pip install -r requirements.txt
```

Now you can generate reports:

```console
$ python report.py aws  # AWS report for yesterday
$ python report.py aws 2020-10-10  # AWS report for a given date
$ python report.py gcp  # GCP report for yesterday
$ python report.py gcp 2020-10-10 | /usr/sbin/sendmail -t  # etc.
```

Alternatively, you can build a Docker image:

```console
$ docker build -t report .
```

and run it:

```console
$ docker run --volume \
      $(pwd)/config.json:config.json:ro \
      report aws

$ docker run --volume \
      $(pwd)/config.json:config.json:ro \
      ~/.config/gcloud/:/root/.config/gcloud:ro \
      report gcp 2019-12-31
```

## Timing

Billing data (on both AWS and GCP) are not provided in real time. In
particular,

* AWS billing data usually lands in S3 between 6-12 hours after the end of the
  day. For example, billing data for the time period between 00:00 PT
  September 15, 2020 and 23:59 PT September 15, 2020 will generally be available
  for download by 06:00 PT September 16, 2020.

* GCP billing data usually lands in GCS between 12-18 hours after the end of the
  day. So, for example, billing data for the time period between 00:00 PT
  September 15, 2020 and 23:59 PT September 15, 2020 will generally be available
  for download by 17:00 PT September 16, 2020.

These observations are general and not always the case. For example, at the
beginning of the billing period (the first few days of the month), billing data
may not be available at all.

## Internal use

Erich runs these reports via Docker daily; generating AWS reports at 6 AM PT and
GCP reports at 5 PM PT. As mentioned above, this means that some reports may
fail to generate on time, especially at the beginning of the month. To address
this, there's some retry logic (see retry-failed-reports.py) to track and
automatically retry generating those reports.

The cron jobs look something like this:

```
SHELL=/bin/bash
0 6 * * * root (docker run -v /root/reporting/config.json:/config.json:ro ghcr.io/ucsc-cgp/cloud-billing-report:latest aws > /tmp/aws.eml && sendmail -t < /tmp/aws.eml) || echo "aws,$(date -v-1d +%Y-%m-%d)" >> /root/reporting/fail.log
0 17 * * * root (docker run -v /root/reporting/config.json:/config.json:ro -v /root/.config/gcloud:/root/.config/gcloud:ro ghcr.io/ucsc-cgp/cloud-billing-report:latest gcp > /tmp/gcp.eml && sendmail -t < /tmp/gcp.eml) || echo "gcp,$(date -v-1d +%Y-%m-%d)" >> /root/reporting/fail.log
0 19 * * * root python /root/reporting/retry-failed-reports.py /root/reporting/fail.log
```

Note that the last job, `retry-failed-reports.py`, needs to be run with Python
3.
