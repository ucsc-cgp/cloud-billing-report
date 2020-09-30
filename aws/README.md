# AWS Billing Report

Given an AWS Cost and Usage Report stored in an S3 bucket, compiles a report
with historical expense information for a number of specified AWS accounts and
sends that report to specified recipients.

You can install dependencies with

    $ cpanm --installdeps .

and run the script with

    $ perl report_aws_spending


## Configuration

Copy the file [config.pl.example](config.pl.example) to
`/root/aws-reporting/config.pl` and complete it with:
* Email addresses of report recipients
* Account names and numbers to check
* AWS access keys
* S3 bucket name containing billing data

### Known issues

If AWS is refusing your requests with a 403 error and you know that your keys
and permissions are correctly configured, it's likely that the container clock
has drifted (which can happen on macOS). See the [Docker documentation][clock]
or run:

    $ docker run --rm --privileged alpine hwclock -s

Also refer to this [Stack Overflow answer]. You're also going to want to check
the `TZ` environment variable in docker-compose.yml; the script will check the
database for records based on the current day. If the time zone is set
incorrectly, you may not see the results you expect.

  [clock]: https://docs.docker.com/docker-for-mac/troubleshoot/#known-issues
  [answer]: https://stackoverflow.com/a/39046197/317076

### Without Docker

If you're installing without using Docker, you can install dependencies with

    $ cpanm --installdeps .

It will be useful to look at the install process outlined in the `Dockerfile`.

Be careful replicating the development environment on your local machine,
especially if you are running macOS. One of the dependencies
(LWP::Protocol::https) appears to, in some cases, interfere with an existing
installation of openssl. (This can break tools that communicate over https.)

### Testing

You might encounter issues testing this script locally depending on what
recipients are specified. (For example, Google will not accept mail from some
hosts over IPv6 without extra configuration.) In this case, the script can be
modified to output the email report to a file.

Alternatively, you can configure `postfix` to use an external mail server.
Here's a [guide](https://gist.github.com/kany/c44c077881047ead8faa) on how
to set up Postfix to relay email sent from your machine to Gmail on macOS.
