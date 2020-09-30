# GCP Billing Report

Given GCP billing data stored in an GCS bucket, compiles a report with
historical expense information for a number of specified GCP projects and sends
that report to specified recipients.

You can install dependencies with

    $ cpanm --installdeps .

and run the script with

    $ perl report_gcp_spending


## Configuration

Copy `config.pl.example` to `config.pl`. The fields are more or less
self-explanatory. You'll need access to billing data in GCS. You can configure
access by installing the Google Cloud SDK (`brew cask install google-cloud-sdk`,
or something like that) then doing `gcloud auth login`.

### Without Docker

If you're installing without using Docker, you can install dependencies with

    $ cpanm --installdeps .

It will be useful to look at the install process outlined in the `Dockerfile`.

Be careful replicating the development environment on your local machine,
especially if you are running macOS. One of the dependencies
(LWP::Protocol::https) appears to, in some cases, interfere with an existing
installation of openssl. (This can break tools that communicate over https.)

If you're committed to the endeavor, MySQL bindings need to be installed and
need special configuration to work. On macOS, you need to `brew install
mysql-connector-c` and `brew install mysql` and link/unlink both of them in
some arcane order so you can configure MySQL in the right way so that cpan
knows to look for openssl libraries in the right place. (This exercise is left
to the reader.)

### Testing

You might encounter issues testing this script locally depending on what
recipients are specified. (For example, Google will not accept mail from some
hosts over IPv6 without extra configuration.) In this case, the script can be
modified to output the email report to a file.

Alternatively, you can configure `postfix` to use an external mail server.
Here's a [guide](https://gist.github.com/kany/c44c077881047ead8faa) on how
to set up Postfix to relay email sent from your machine to Gmail on macOS.
