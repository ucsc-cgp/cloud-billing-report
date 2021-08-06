"""
Summarizes given billing data for a cloud platform as a .eml printed to stdout.
"""
import argparse
import collections
import csv
from datetime import (
    datetime,
    timedelta,
)
from decimal import (
    Decimal,
)
from email.message import (
    EmailMessage,
)
import gzip
import itertools
import json
import operator
from pathlib import (
    Path,
)
import tempfile
from typing import (
    Iterator,
    Mapping,
    Sequence,
    Union,
)

import boto3
from dateutil.relativedelta import (
    relativedelta,
)
from google.cloud import (
    bigquery,
)
import jinja2

from src.compliance_report import compliance_report
from src.Boto3_STS_Service import Boto3_STS_Service

import uuid
from pathlib import Path
from src.report_resource import report_resource


class Report:
    UNTAGGED = '(untagged)'

    def __init__(self, *, platform: str, date: datetime.date, config_path: str):
        self.platform = platform
        self.date = date

        with open(config_path, 'r') as config_json:
            self._config = json.load(config_json)[platform]

        self.jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'))
        self.jinja_env.filters.update({
            'print_amount': print_amount,
            'ymd': lambda d: d.strftime('%Y/%m/%d'),
            'ym': lambda d: d.strftime('%Y/%m'),
            'nested_sum_values': lambda m: sum(sum(k.values()) for k in m.values()),
            'sum_values': lambda m: sum(m.values()),
            'sum_key': lambda rows, key: sum(row[key] for row in rows),
            'group_by': group_by,
            'filter_by': filter_by,
            'print_diff': lambda a: print_diff(a, self.warning_threshold)
        })

    @property
    def bucket(self) -> str:
        return self._config['bucket']

    @property
    def warning_threshold(self) -> int:
        try:
            return self._config['warning_threshold']
        except KeyError:
            return 200

    @property
    def email_from(self) -> str:
        return self._config['from']

    @property
    def email_recipients(self) -> Sequence:
        return self._config['recipients']

    @property
    def access_key(self) -> str:
        assert self.platform == 'aws'
        return self._config['access_key']

    @property
    def secret_key(self) -> str:
        assert self.platform == 'aws'
        return self._config['secret_key']

    @property
    def report_prefix(self) -> str:
        assert self.platform == 'aws'
        return self._config['prefix']

    @property
    def report_name(self) -> str:
        assert self.platform == 'aws'
        return self._config['report_name']

    @property
    def accounts(self) -> Mapping:
        assert self.platform == 'aws'
        return self._config['accounts']

    @property
    def compliance(self) -> Mapping:
        assert self.platform == 'aws'
        return self._config['compliance']

    @property
    def bigquery_table(self) -> str:
        assert self.platform == 'gcp'
        return self._config['bigquery_table']

    def render_email(self,
                     recipients: Union[str, Sequence[str]],
                     **template_vars) -> str:
        msg = EmailMessage()
        subject_date = self.date.strftime('%B %d, %Y')
        subject = f'{self.platform.upper()} Report for {subject_date}'
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = recipients
        tmpl = self.jinja_env.get_template(f'{self.platform}_report.html')
        body = tmpl.render(report_date=self.date, **template_vars)
        msg.set_content(body, subtype='html')
        return msg.as_string()

    def render_personalized_email(self, recipient: str, resources: list):
        msg = EmailMessage()
        subject_date = self.date.strftime('%B %d, %Y')
        subject = f'{self.platform.upper()} Report for {subject_date}'
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = recipient
        template = self.jinja_env.get_template('personalized_report.html')
        body = template.render(report_date=self.date, resource_list=resources)
        msg.set_content(body, subtype='html')
        return msg.as_string()


class AWSReport(Report):
    # TODO: Should move this into a config file. Holding off for now as there is a config refactor in the near future
    RESOURCE_SHORTHAND = {"Amazon Elastic Compute Cloud": "AWS EC2",
                          "Amazon Simple Storage Service": "AWS S3 Bucket",
                          "Amazon Elastic Block Store": "AWS EBS"}

    def __init__(self, config_path: str, date: datetime.date):
        super().__init__(platform='aws', config_path=config_path, date=date)

    def usage_csv(self) -> Iterator[str]:
        """Return the lines of the latest billing CSV for the given month."""
        s3 = boto3.client('s3',
                          aws_access_key_id=self.access_key,
                          aws_secret_access_key=self.secret_key)
        this_month = self.date.strftime('%Y%m01')
        next_month = (self.date + relativedelta(months=1)).strftime('%Y%m01')
        manifest_path = Path(self.report_prefix)
        manifest_path /= self.report_name
        manifest_path /= f'{this_month}-{next_month}'
        manifest_path /= f'{self.report_name}-Manifest.json'
        with tempfile.TemporaryFile() as tmp:
            s3.download_fileobj(self.bucket, manifest_path.as_posix(), tmp)
            # Reports that are sufficiently large can be split into multiple files
            # but we'll ignore that for now
            tmp.seek(0)
            s3_report_archive_path = json.load(tmp)['reportKeys'][0]
        with tempfile.NamedTemporaryFile() as tmp:
            s3.download_fileobj(self.bucket, s3_report_archive_path, tmp)
            with gzip.open(tmp.name, 'r') as report_fp:
                return report_fp.read().decode().splitlines()

    def generate_compliance_list(self) -> list:

        # start service
        bss = Boto3_STS_Service()

        # get compliance dict from the config file
        compliance_config = self.compliance

        # Create the list of accounts, role arns, and regions that we need to query AWS Config for
        account_id_list = []
        account_name_list = []
        arn_list = []
        region_list = compliance_config["regions"]
        for k in compliance_config["accounts"]:
            account_id_list.append(k)
            account_name_list.append(compliance_config["accounts"][k])
            arn_list.append(f"arn:aws:iam::{k}:role/{compliance_config['iam_role_name']}")

        cr = compliance_report()
        compliance_list = cr.generate_full_compliance_report(bss, account_id_list, account_name_list, arn_list, region_list)

        return compliance_list

    def generate_personalized_compliance_reports(self, compliant_resources: list, report_dir="/tmp/personalizedEmails/") -> str:
        # TODO Most billing reports are showing $0.00 for the S3 costs... may need to rethink
        # Create a dictionary, where the key is the email address and the value is the list of resources
        account_resource_dict = {}
        for resource in compliant_resources:

            # The email address can be none if the tag included 'shared'
            if resource.get_email() is not None:
                if resource.get_email() in account_resource_dict:
                    account_resource_dict[resource.get_email()].append(resource)
                else:
                    account_resource_dict[resource.get_email()] = [resource]

        # For every email in our dictionary, generate an email report, make sure the nested directory exists
        Path(report_dir).mkdir(parents=True, exist_ok=True)
        for email in account_resource_dict:
            eml_text = self.render_personalized_email(
                email,
                account_resource_dict[email]
            )
            with open(f"{report_dir}{email[0:email.find('@')]}-{uuid.uuid4().hex}.eml", "w") as eml_file:
                eml_file.write(eml_text)

    def generate_report(self) -> str:
        report_csv_lines = self.usage_csv()
        report_csv = csv.DictReader(report_csv_lines)
        service_by_account = nested_dict()
        service_by_account_today = nested_dict()
        ec2_owner_by_account = nested_dict()
        ec2_owner_by_account_today = nested_dict()
        ec2_by_name = collections.defaultdict(Decimal)
        ec2_by_name_today = collections.defaultdict(Decimal)
        resource_by_id = {}
        today = self.date.strftime('%Y-%m-%d')

        # Create a list of resource objects based on their compliance status
        compliance_list = self.generate_compliance_list()
        compliant_resources = [r for r in compliance_list if r.get_compliance_status() == "COMPLIANT"]
        noncompliant_resources = [r for r in compliance_list if r.get_compliance_status() == "NON_COMPLIANT"]

        # *** Currently set to run everyday ***
        # For Monday only reports: 'if datetime.strptime(today, "%Y-%m-%d").today().weekday() == 0'
        self.generate_personalized_compliance_reports(compliant_resources)

        # create list of noncompliant resources
        noncompliant_resource_by_account = {self.compliance["accounts"][account_id]: [] for account_id in self.compliance["accounts"]}
        for resource in noncompliant_resources:
            noncompliant_resource_by_account[resource.get_account_name()].append(resource)

        # Populate the dictionaries used for the daily global report
        for row in report_csv:
            account = self.accounts.get(row['lineItem/UsageAccountId'], '(unknown)')  # account for resource
            service = row['product/ProductName']  # which type of product this is
            amount = Decimal(row['lineItem/BlendedCost'])  # the cost associated with this
            when = row['lineItem/UsageStartDate'][0:10]  # ISO8601
            owner = row['resourceTags/user:Owner'] or row['resourceTags/user:owner'] or self.UNTAGGED  # owner of the resource, untagged if none specified
            name = row['resourceTags/user:Name'] or self.UNTAGGED  # name of the resource, untagged if none specified
            resource_id = row['lineItem/ResourceId']  # resource id, not necessarily the arn
            region = row['product/region'] # The region the product was billed from

            # monthly cost summary of the resource
            if len(resource_id) > 0:
                if resource_id not in resource_by_id:
                    resource_by_id[resource_id] = report_resource(resource_id, service, '', account, region)
                    resource_by_id[resource_id].set_resource_url()

                if row['resourceTags/user:Owner']:
                    resource_by_id[resource_id].add_tag_value("Owner", row['resourceTags/user:Owner'])
                elif row['resourceTags/user:owner']:
                    resource_by_id[resource_id].add_tag_value("owner", row['resourceTags/user:owner'])
                resource_by_id[resource_id].add_to_monthly_cost(amount)

            if when == today:
                service_by_account_today[account][service] += amount
                service_by_account[account][service] += amount
                if service == 'Amazon Elastic Compute Cloud':
                    ec2_by_name_today[name] += amount
                    ec2_by_name[name] += amount
                    ec2_owner_by_account_today[account][owner] += amount
                    ec2_owner_by_account[account][owner] += amount
            elif when < today:
                service_by_account[account][service] += amount
                if service == 'Amazon Elastic Compute Cloud':
                    ec2_by_name[name] += amount
                    ec2_owner_by_account[account][owner] += amount

        top_resources = dict(sorted(resource_by_id.items(), key=lambda x: x[1].monthly_cost, reverse=True)[:30])

        return self.render_email(
            self.email_recipients,
            service_by_account=service_by_account,
            service_by_account_today=service_by_account_today,
            ec2_owner_by_account=ec2_owner_by_account,
            ec2_owner_by_account_today=ec2_owner_by_account_today,
            ec2_by_name=ec2_by_name,
            ec2_by_name_today=ec2_by_name_today,
            noncompliant_resource_by_account=noncompliant_resource_by_account,
            top_resources=top_resources
        )


class GCPReport(Report):

    def __init__(self, config_path: str, date: datetime.date):
        super().__init__(platform='gcp', config_path=config_path, date=date)

    def generate_report(self) -> str:
        client = bigquery.Client()
        query_month = self.date.strftime('%Y%m')
        query_today = self.date.strftime('%Y-%m-%d')

        # noinspection SqlNoDataSourceInspection
        query = f'''SELECT
              project.name,
              service.description,
              SUM(cost) + SUM(IFNULL(creds.amount, 0)) AS cost_month,
              SUM(CASE WHEN DATE(usage_start_time) = '{query_today}' THEN cost ELSE 0 END) +
              SUM(CASE WHEN DATE(usage_start_time) = '{query_today}'
                       THEN IFNULL(creds.amount, 0) ELSE 0 END) as cost_today
            FROM `{self.bigquery_table}`
            LEFT JOIN UNNEST(credits) AS creds
            WHERE invoice.month = '{query_month}' AND DATE(usage_start_time) <= '{query_today}'
            GROUP BY project.name, service.description
            ORDER BY LOWER(project.name) ASC, service.description ASC'''
        query_job = client.query(query)
        rows = list(query_job.result())
        return self.render_email(self.email_recipients, rows=rows)


def print_amount(amount: Union[Decimal, float, int]) -> str:
    """
    >>> from decimal import Decimal
    >>> print_amount(Decimal('20.000000000000000001'))
    '$20.00'

    >>> print_amount(Decimal('-10'))
    '-$10.00'
    """
    amount = Decimal(amount).quantize(Decimal('0.01'))
    symbol = '-' if amount < 0 else ''
    return f'{symbol}${abs(amount)}'


def print_diff(amount: Decimal, threshold: int = 200) -> str:
    """
    >>> from decimal import Decimal
    >>> print_diff(Decimal('100.00'))
    '$100.00'

    >>> print_diff(Decimal('100'))
    '$100.00'

    >>> print_diff(Decimal('0.00'))
    ''

    >>> print_diff(Decimal('101'), 100)
    '<span class="unusual">$101.00</span>'

    >>> print_diff(Decimal('-0.02'))
    '<span class="unusual">-$0.02</span>'
    """
    if amount > threshold or amount < 0:
        return f'<span class="unusual">{print_amount(amount)}</span>'
    elif amount < Decimal('0.01'):
        return ''
    else:
        return print_amount(amount)


def nested_dict():
    """
    >>> from decimal import Decimal
    >>> service_by_account = nested_dict()
    >>> service_by_account['foo-account']['bar-service'] += Decimal('1.00')
    >>> print(service_by_account['foo-account']['bar-service'])
    1.00
    """
    return collections.defaultdict(lambda: collections.defaultdict(Decimal))


def filter_by(rows: Sequence[Mapping], **conditions) -> Iterator[Mapping]:
    """
    >>> my_rows = [
    ...     {'foo': 1, 'bar': 2, 'baz': 3},
    ...     {'foo': 1, 'bar': 3, 'baz': 2},
    ...     {'foo': 2, 'bar': 2, 'baz': 1}
    ... ]

    >>> list(filter_by(my_rows, bar=2))
    [{'foo': 1, 'bar': 2, 'baz': 3}, {'foo': 2, 'bar': 2, 'baz': 1}]

    >>> list(filter_by(my_rows, bar=2, foo=2))
    [{'foo': 2, 'bar': 2, 'baz': 1}]
    """
    return (row for row in rows if dict(row).items() >= conditions.items())


def group_by(rows: Sequence[Mapping[str, int]],
             key: str,
             *targets: str,
             **conditions) -> Iterator[Sequence[int]]:
    """
    SELECT key, SUM(target1), ..., SUM(targetn) FROM ... WHERE conditions GROUP BY key
    >>> my_rows = [
    ...     {'foo': 1, 'bar': 2, 'baz': 3},
    ...     {'foo': 1, 'bar': 3, 'baz': 2},
    ...     {'foo': 2, 'bar': 2, 'baz': 1}
    ... ]

    >>> list(group_by(my_rows, 'foo', 'bar'))
    [(1, 5), (2, 2)]

    >>> list(group_by(my_rows, 'foo', 'bar', 'baz'))
    [(1, 5, 5), (2, 2, 1)]

    >>> list(group_by(my_rows, 'foo', 'bar', 'baz', baz=2))
    [(1, 3, 2)]
    """
    grouped = (
        (k, list(v))
        for k, v in itertools.groupby(filter_by(rows, **conditions), key=operator.itemgetter(key))
    )
    return (
        (k, *(sum(val[target] for val in vals) for target in targets))
        for k, vals in grouped
    )


report_types = {
    'aws': AWSReport,
    'gcp': GCPReport
}

if __name__ == '__main__':
    # https://youtrack.jetbrains.com/issue/PY-41806
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    date_format = '%Y-%m-%d'
    parser.add_argument('report_type',
                        choices=report_types.keys(),
                        help='Platform to generate a report for.')
    parser.add_argument('report_date',
                        default=(datetime.now() - timedelta(days=1)).strftime(date_format),
                        nargs='?',
                        help='YYYY-MM-DD to generate a report for. Defaults to yesterday.')
    parser.add_argument('--config',
                        default=Path.cwd() / 'config.json',
                        help='Path to config.json. Default to current directory.')
    arguments = parser.parse_args()
    date = datetime.strptime(arguments.report_date, date_format).date()
    report = report_types[arguments.report_type](arguments.config, date)
    print(report.generate_report())
