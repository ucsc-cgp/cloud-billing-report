# GCP Billing Report

Given GCP billing data stored in an GCS bucket and a MySQL database, compiles
a report with historical expense information for a number of specified GCP
projects and sends that report to a number of recipients.

You can install dependencies with

    $ cpanm --installdeps .

and run the script with

    $ perl report_gcp_spending


## Configuration

Copy `config.pl.example` to `config.pl`. The fields are more or less
self-explanatory.


## Development

To run this script locally, you'll need a few things:
* A `mysqldump` of the database that stores historical spend information (that
  this script accesses). If you don't have this, it may be sufficient to create
  a table for each account in `accounts.csv`. Store this file in a subdirectory
  named `db/`; `docker-compose` will automatically populate the database with
  this data.
* GCP keys with access to billing data in GCS. You'll need to install the
  Google Cloud SDK (`brew cask install google-cloud-sdk` or something like
  that) and then copy the configuration directory to this directory
  (`cp -R ~/.config/gcloud/ gcloud/`). I haven't found a better way to do this
  yet.
* `docker-compose`

Then:

    $ docker-compose up --abort-on-container-exit

will run the script.

Before running the script, the script should be modified to output the report
to a file, or something else besides piping it to `sendmail`. The Docker
container does not have postfix installed, so without this change, the script
will fail. This can be accomplished by replacing

    open(MAILSEND, "|/usr/sbin/sendmail -t");

with something like

    open(MAILSEND, "| tee report.html");

You can then open the generated report in your browser.


### Known bugs

If the report service starts before the database service is finished starting,
the script will fail and restart until it succeeds. Each restart downloads
files from GCS, so be cognizant of this and kill it if it isn't working.

This should only be a problem the first time the script is run, or if anonymous
volumes are manually purged (as with `docker up --renew-anon-volumes`).

### Without docker-compose

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
