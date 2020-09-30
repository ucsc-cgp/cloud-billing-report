# cloud-billing-report

Perl scripts that parse AWS and GCP billing data and generate an email report.
Written by Erich Weiler.

This repository was previously named ucsc-cgp/aws-billing-report. It was
renamed ucsc-cgp/cloud-billing-report to accomodate reporting scripts for both
AWS and GCP.

## Development

Generating reports locally is easiest with Docker, which is helpful in avoiding
dependency purgatory:

```console
$ make -C aws report   # Deposits report in aws/report.eml
$ make -C gcp report   # Same as above, but gcp/report.eml
$ make -C aws send     # If sendmail is configured, generate aws/report.eml then
                       # send
$ REPORT_DATE=YYYY-MM-DD make -C aws send    # Reports for past dates
$ REPORT_DATE=YYYY-MM-DD make -C gcp report  # This works, too!
```

## Housekeeping

### Commits

Commit messages for work that pertains only to one report should be prefixed
with `gcp: ` or `aws: `, a la

    gcp: Reticulate splines

. If the commits affects both reports (or neither report) it can be left without
a prefix. This makes it easier to identify changes between versions.

Generally, I would take this as an indication that we need two different repos,
but that seems like a hassle so this can stay for now.

### Versions

Scripts are not explicitly versioned, but are tagged based on when they are
"released" to Erich for installation in format `report_type/YYYY-MM-DD`,
e.g. `aws/2020-08-11` or `gcp/1999-01-02`.

