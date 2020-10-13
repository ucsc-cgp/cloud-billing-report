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

