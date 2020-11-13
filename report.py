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
import gzip
import itertools
import json
import operator
import os
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


class Config:

    def __init__(self, platform: str, path: str):
        assert platform in report_types
        self._platform = platform
        with open(path, 'r') as config_json:
            self._config = json.load(config_json)

    @property
    def bucket(self) -> str:
        return self._config[self._platform]['bucket']

    @property
    def warning_threshold(self) -> int:
        try:
            return self._config[self._platform]['warning_threshold']
        except KeyError:
            return 200

    @property
    def email_from(self) -> str:
        return self._config[self._platform]['from']

    @property
    def email_recipients(self) -> Sequence:
        return self._config[self._platform]['recipients']

    @property
    def access_key(self) -> str:
        assert self._platform == 'aws'
        return self._config[self._platform]['access_key']

    @property
    def secret_key(self) -> str:
        assert self._platform == 'aws'
        return self._config[self._platform]['secret_key']

    @property
    def report_prefix(self) -> str:
        assert self._platform == 'aws'
        return self._config[self._platform]['prefix']

    @property
    def report_name(self) -> str:
        assert self._platform == 'aws'
        return self._config[self._platform]['report_name']

    @property
    def accounts(self) -> Mapping:
        assert self._platform == 'aws'
        return self._config[self._platform]['accounts']

    @property
    def bigquery_table(self) -> str:
        assert self._platform == 'gcp'
        return self._config[self._platform]['bigquery_table']


def report_aws(report_date: datetime.date, config_path: str) -> str:
    config = Config('aws', path=config_path)
    s3 = boto3.client('s3',
                      aws_access_key_id=config.access_key,
                      aws_secret_access_key=config.secret_key)
    this_month = report_date.strftime('%Y%m01')
    next_month = (report_date + relativedelta(months=1)).strftime('%Y%m01')
    manifest_path = os.path.join(config.report_prefix,
                                 config.report_name,
                                 f'{this_month}-{next_month}',
                                 f'{config.report_name}-Manifest.json')
    with tempfile.TemporaryFile() as tmp:
        s3.download_fileobj(config.bucket, manifest_path, tmp)
        # Reports that are sufficiently large can be split into multiple files
        # but we'll ignore that for now
        tmp.seek(0)
        s3_report_archive_path = json.load(tmp)['reportKeys'][0]
    with tempfile.NamedTemporaryFile() as tmp:
        s3.download_fileobj(config.bucket, s3_report_archive_path, tmp)
        with gzip.open(tmp.name, 'r') as report_fp:
            report_csv_lines = report_fp.read().decode().splitlines()

    report_csv = csv.DictReader(report_csv_lines)
    service_by_account = nested_dict()
    service_by_account_today = nested_dict()
    ec2_owner_by_account = nested_dict()
    ec2_owner_by_account_today = nested_dict()
    ec2_by_name = collections.defaultdict(Decimal)
    ec2_by_name_today = collections.defaultdict(Decimal)
    today = report_date.strftime('%Y-%m-%d')

    for row in report_csv:
        account = config.accounts.get(row['lineItem/UsageAccountId'], '(unknown)')
        service = row['product/ProductName']
        amount = Decimal(row['lineItem/BlendedCost'])
        when = row['lineItem/UsageEndDate'][0:10]  # ISO8601

        if when == today:
            service_by_account_today[account][service] += amount
            service_by_account[account][service] += amount
            if service == 'Amazon Elastic Compute Cloud':
                owner = row['resourceTags/user:Owner'] or '(untagged)'
                name = row['resourceTags/user:Name'] or '(untagged)'
                ec2_by_name_today[name] += amount
                ec2_by_name[name] += amount
                ec2_owner_by_account_today[account][owner] += amount
                ec2_owner_by_account[account][owner] += amount
        elif when < today:
            service_by_account[account][service] += amount
            if service == 'Amazon Elastic Compute Cloud':
                owner = row['resourceTags/user:Owner'] or '(untagged)'
                name = row['resourceTags/user:Name'] or '(untagged)'
                ec2_by_name[name] += amount
                ec2_owner_by_account[account][owner] += amount

    env.filters['print_diff'] = lambda a: print_diff(a, config.warning_threshold)
    return env.get_template('aws_report.html').render(
        report_date=report_date,
        service_by_account=service_by_account,
        service_by_account_today=service_by_account_today,
        ec2_owner_by_account=ec2_owner_by_account,
        ec2_owner_by_account_today=ec2_owner_by_account_today,
        ec2_by_name=ec2_by_name,
        ec2_by_name_today=ec2_by_name_today,
        email_from=config.email_from,
        email_recipients=config.email_recipients
    )


def report_gcp(report_date: datetime.date, config_path: str) -> str:
    config = Config('gcp', path=config_path)
    client = bigquery.Client()
    query_month = report_date.strftime('%Y%m')
    query_today = report_date.strftime('%Y-%m-%d')
    # noinspection SqlNoDataSourceInspection
    query = f'''SELECT project.name, service.description,
          SUM(cost) + SUM(IFNULL(creds.amount, 0)) AS cost_month,
          SUM(CASE WHEN DATE(usage_start_time) = '{query_today}'
                   THEN cost ELSE 0 END) +
          SUM(CASE WHEN DATE(usage_start_time) = '{query_today}'
                   THEN IFNULL(creds.amount, 0) ELSE 0 END) as cost_today
        FROM `{config.bigquery_table}`
        LEFT JOIN UNNEST(credits) AS creds
        WHERE invoice.month = '{query_month}' AND DATE(usage_start_time) <= '{query_today}'
        GROUP BY project.name, service.description
        ORDER BY LOWER(project.name) ASC, service.description ASC'''
    query_job = client.query(query)
    rows = list(query_job.result())
    env.filters['print_diff'] = lambda a: print_diff(a, config.warning_threshold)
    return env.get_template('gcp_report.html').render(
        rows=rows,
        report_date=report_date,
        email_from=config.email_from,
        email_recipients=config.email_recipients
    )


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


def group_by(rows, key: str, *targets: str, **conditions):
    """
    SELECT key, SUM(target1), ..., SUM(targetn) FROM ... WHERE conditions GROUP BY key
    >>> my_rows = [
    ...     {'foo': 1, 'bar': 2, 'baz': 3},
    ...     {'foo': 1, 'bar': 3, 'baz': 2},
    ...     {'foo': 2, 'bar': 2, 'baz': 1}
    ... ]

    >>> group_by(my_rows, 'foo', 'bar')
    [(1, 5), (2, 2)]

    >>> group_by(my_rows, 'foo', 'bar', 'baz')
    [(1, 5, 5), (2, 2, 1)]

    >>> group_by(my_rows, 'foo', 'bar', 'baz', baz=2)
    [(1, 3, 2)]
    """
    grouped = (
        (k, list(v))
        for k, v in itertools.groupby(filter_by(rows, **conditions), key=operator.itemgetter(key))
    )
    return [
        (k, *(sum(val[target] for val in vals) for target in targets))
        for k, vals in grouped
    ]


report_types = {
    'gcp': report_gcp,
    'aws': report_aws
}

env = jinja2.Environment(loader=jinja2.FileSystemLoader('templates/'))
env.filters.update({
    'print_amount': print_amount,
    'ymd': lambda d: d.strftime('%Y/%m/%d'),
    'ym': lambda d: d.strftime('%Y/%m'),
    'nested_sum_values': lambda m: sum(sum(k.values()) for k in m.values()),
    'sum_values': lambda m: sum(m.values()),
    'sum_key': lambda rows, key: sum(row[key] for row in rows),
    'group_by': group_by,
    'filter_by': filter_by
})

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
                        default=os.path.join(os.getcwd(), 'config.json'),
                        help='Path to config.json. Default to current directory.')
    arguments = parser.parse_args()
    date = datetime.strptime(arguments.report_date, date_format).date()
    report = report_types[arguments.report_type](date, arguments.config)
    print(report)
