"""
Summarizes given billing data for a cloud platform as a .eml printed to stdout.
"""
import argparse
import collections
import csv
import datetime
from decimal import (
    Decimal,
)
from email.message import (
    EmailMessage,
)
import gzip
import io
import itertools
import json
import numbers
import operator
from pathlib import (
    Path,
)
import re
import sys
import tempfile
from typing import (
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Union,
)
import uuid

import boto3
from dateutil.relativedelta import (
    relativedelta,
)
from google.cloud import (
    bigquery,
)
import jinja2

from src.Boto3_STS_Service import (
    Boto3_STS_Service,
)
from src.compliance_report import (
    compliance_report,
)
from src.report_resource import (
    report_resource,
)


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
            'sort_by': sort_by,
            'to_project_id': lambda value: 'project-' + to_id(value),
            'to_service_id': lambda value: 'service-' + to_id(value),
            'print_diff': lambda a: print_diff(a, self.warning_threshold),
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

    @property
    def terra_workspaces_path(self) -> str:
        assert self.platform == 'gcp'
        return self._config.get('terra_workspaces_path')

    def render_email(self,
                     report_date: datetime.date,
                     recipients: Union[str, Sequence[str]],
                     **template_vars) -> str:
        msg = EmailMessage()
        subject_date = self.date.strftime('%B %d, %Y')
        subject = f'{self.platform.upper()} Report for {subject_date}'
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = recipients
        tmpl = self.jinja_env.get_template(f'{self.platform}_report.html')
        body = tmpl.render(report_date=report_date, **template_vars)
        msg.set_content(body, subtype='html')
        return msg.as_string()

    def render_personalized_email(self,
                                  report_date: datetime.date,
                                  recipient: str,
                                  resources: list):
        msg = EmailMessage()
        subject_date = self.date.strftime('%B %d, %Y')
        subject = f'{self.platform.upper()} Report for {subject_date}'
        msg['Subject'] = subject
        msg['From'] = self.email_from
        msg['To'] = recipient
        template = self.jinja_env.get_template('personalized_report.html')
        body = template.render(report_date=report_date, resource_list=resources)
        msg.set_content(body, subtype='html')
        return msg.as_string()

    def firstDayOfMonth(self, date: datetime.date) -> datetime.date:
        return date.replace(day=1)

    def lastDayOfMonth(self, date: datetime.date) -> datetime.date:
        return datetime.date(date.year + (date.month == 12),
            (date.month + 1 if date.month < 12 else 1), 1) - datetime.timedelta(1)

    def daysOfMonthUpToAndIncluding(self, date: datetime.date) -> Sequence[datetime.date]:
        firstDayOfMonth = self.firstDayOfMonth(date)
        return [firstDayOfMonth + datetime.timedelta(days=offset) for offset in range((date - firstDayOfMonth).days + 1)]

    def saveFile(self, fileName: str, content: str) -> None:
        print("OBJECT-NAME: ", fileName)
        sys.stdout.write(content);
        # TODO write to bucket

    def generateFileName(self, prefix: str, extension: str, date: datetime.date) -> str:
        return f'{self.platform}/{date.year}/{date.month}/{prefix}-{self.platform}-{date.year}-{date.month}.{extension}'

    def generateBillingCsvFileName(self, date: datetime.date) -> str:
        return self.generateFileName('cost-', 'csv', date)

    def toCsv(self, rows: Sequence[Mapping[str, str]]) -> str:
        with io.StringIO('') as file:
            csvWriter = csv.DictWriter(file, fieldnames=rows[0].keys())
            csvWriter.writeheader()
            for row in rows:
                csvWriter.writerow(row)
            return file.getvalue()


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
        # Get the list of S3 report object keys
        with tempfile.TemporaryFile() as tmp:
            s3.download_fileobj(self.bucket, manifest_path.as_posix(), tmp)
            # Reports that are sufficiently large can be split into multiple files
            # but we'll ignore that for now
            tmp.seek(0)
            reportKeys = json.load(tmp)['reportKeys']
        # Create a list of the lines from each of the report object files
        allLines = []
        for s3_report_archive_path in reportKeys:
            with tempfile.NamedTemporaryFile() as tmp:
                s3.download_fileobj(self.bucket, s3_report_archive_path, tmp)
                tmp.flush()
                with gzip.open(tmp.name, 'r') as report_fp:
                    fileLines = report_fp.read().decode().splitlines()
                    allLines.extend(fileLines)
        return allLines

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
        compliance_list = cr.generate_full_compliance_report(bss, account_id_list, account_name_list, arn_list,
                                                             region_list)

        return compliance_list

    def generatePersonalizedComplianceReports(self,
                                              reportDate: datetime.date,
                                              compliant_resources: list,
                                              noncompliant_resources: list,
                                              report_dir="/tmp/personalizedEmails/") -> str:
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

        for resource in noncompliant_resources:
            if "righanse@ucsc.edu" in account_resource_dict:
                account_resource_dict["righanse@ucsc.edu"].append(resource)
            else:
                account_resource_dict["righanse@ucsc.edu"] = [resource]

        # For every email in our dictionary, generate an email report, make sure the nested directory exists
        Path(report_dir).mkdir(parents=True, exist_ok=True)
        for email in account_resource_dict:
            eml_text = self.render_personalized_email(
                reportDate,
                email,
                account_resource_dict[email]
            )
            with open(f"{report_dir}{email[0:email.find('@')]}-{uuid.uuid4().hex}.eml", "w") as eml_file:
                eml_file.write(eml_text)

    def generateComplianceSummary(self, reportDate: datetime.date):
        # Create a list of resource objects based on their compliance status
        compliance_list = self.generate_compliance_list()
        compliant_resources = [r for r in compliance_list if r.get_compliance_status() == "COMPLIANT"]
        noncompliant_resources = [r for r in compliance_list if r.get_compliance_status() == "NON_COMPLIANT"]

        # *** Currently set to run everyday ***
        # For Monday only reports: 'if datetime.strptime(today, "%Y-%m-%d").today().weekday() == 0'
        self.generatePersonalizedComplianceReports(reportDate, compliant_resources, noncompliant_resources)

    def generateAccountSummary(self, accounts, startDate: datetime.date, endDate: datetime.date):

        accountIds = list(accounts.keys())

        startDate = startDate.strftime("%Y-%m-%d")
        endDate = endDate.strftime("%Y-%m-%d")

        billingClient = boto3.client('ce',
                                     aws_access_key_id=self.access_key,
                                     aws_secret_access_key=self.secret_key)

        # Make the request
        result = billingClient.get_cost_and_usage(
            TimePeriod={
                'Start': startDate,
                'End': endDate
            },
            Granularity="MONTHLY",
            Filter={
                "And": [
                    {
                        "Not": {
                            "Dimensions": {
                                "Key": "RECORD_TYPE",
                                "Values": ["Credit", "Refund"]
                            }
                        }
                    }, {
                        "Dimensions": {
                            "Key": "LINKED_ACCOUNT",
                            "Values": accountIds
                        }
                    }]
            },
            Metrics=["BlendedCost"],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': "LINKED_ACCOUNT"
                }, {
                    'Type': 'DIMENSION',
                    'Key': "SERVICE"
                }
            ]
        )

        # The dictionary we are returning
        returnDict = {}

        assert len(result["ResultsByTime"]) == 1
        timeRange = result["ResultsByTime"][0]

        for group in timeRange["Groups"]:
            # Parse out values
            accountId = group["Keys"][0]
            accountName = accounts[accountId]
            serviceName = group["Keys"][1]
            blendedCost = float(group["Metrics"]["BlendedCost"]["Amount"])

            # Populate the account in the dictionary if it isn't already there, do the same for the service
            returnDict.setdefault(accountName, {})

            # The service should only appear once per account
            assert serviceName not in returnDict[accountName]
            returnDict[accountName][serviceName] = blendedCost

        return returnDict

    def generateUsageTypeSummary(self, accounts, startDate: datetime.date, endDate: datetime.date):

        accountIds = list(accounts.keys())

        startDate = startDate.strftime("%Y-%m-%d")
        endDate = endDate.strftime("%Y-%m-%d")

        billingClient = boto3.client('ce',
                                     aws_access_key_id=self.access_key,
                                     aws_secret_access_key=self.secret_key)

        # Make the request
        result = billingClient.get_cost_and_usage(
            TimePeriod={
                'Start': startDate,
                'End': endDate
            },
            Granularity="MONTHLY",
            Filter={
                "And": [
                    {
                        "Not": {
                            "Dimensions": {
                                "Key": "RECORD_TYPE",
                                "Values": ["Credit", "Refund"]
                            }
                        }
                    }, {
                        "Dimensions": {
                            "Key": "LINKED_ACCOUNT",
                            "Values": accountIds
                        }
                    }]
            },
            Metrics=["BlendedCost"],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': "SERVICE"
                }, {
                    'Type': 'DIMENSION',
                    'Key': "USAGE_TYPE"
                }
            ]
        )

        # The dictionary we are returning
        returnDict = {}

        assert len(result["ResultsByTime"]) == 1
        timeRange = result["ResultsByTime"][0]

        for group in timeRange["Groups"]:
            # Parse out values
            serviceName = group["Keys"][0]
            UsageType = group["Keys"][1]
            blendedCost = float(group["Metrics"]["BlendedCost"]["Amount"])

            # Populate the account in the dictionary if it isn't already there, do the same for the service
            returnDict.setdefault(serviceName, {})

            # The service should only appear once per account
            assert UsageType not in returnDict[serviceName]
            returnDict[serviceName][UsageType] = blendedCost

        return returnDict

    def generateResourceSummary(self, accounts):
        reportCsvLines = self.usage_csv()
        reportCsv = csv.DictReader(reportCsvLines)

        resources = {}

        for row in reportCsv:

            # skip rows that don't involve a cost, typicall those that refer to a discount, credit, or refund
            itemType = row['lineItem/LineItemType']
            if not (itemType.endswith('Usage') or itemType.endswith('Fee') or itemType.endswith('Tax')):
                continue

            account = self.accounts.get(row['lineItem/UsageAccountId'], '(unknown)')  # account for resource

            # Skip this line item if the resource is not in a compliance account
            if account not in accounts.values():
                continue

            service = row['product/ProductName']  # which type of product this is
            usage_type = row['lineItem/UsageType']
            amount = Decimal(row['lineItem/BlendedCost'])  # the cost associated with this
            description = row['lineItem/LineItemDescription']
            resourceId = row['lineItem/ResourceId'] if len(row['lineItem/ResourceId']) > 0 else \
                uuid.uuid4().hex[0:7] + " (" + description + ")"  # resource id, not necessarily the arn
            region = row['product/region']  # The region the product was billed from

            # monthly cost summary of the resource
            resources.setdefault(resourceId, report_resource(resourceId, service, '', account, region))

            if len(row['lineItem/ResourceId']) > 0:
                resources[resourceId].set_resource_url()

            if row['resourceTags/user:Owner']:
                resources[resourceId].add_tag_value("Owner", row['resourceTags/user:Owner'])
            elif row['resourceTags/user:owner']:
                resources[resourceId].add_tag_value("owner", row['resourceTags/user:owner'])
            resources[resourceId].add_to_monthly_cost(amount)
            resources[resourceId].add_usage_type(usage_type, amount)

        return resources

    def generateS3StorageSummary(self, accounts, startDate: datetime.date, endDate: datetime.date):

        accountIds = list(accounts.keys())

        startDate = startDate.strftime("%Y-%m-%d")
        endDate = endDate.strftime("%Y-%m-%d")

        billingClient = boto3.client('ce',
                                     aws_access_key_id=self.access_key,
                                     aws_secret_access_key=self.secret_key)

        # Make the request
        result = billingClient.get_cost_and_usage(
            TimePeriod={
                'Start': startDate,
                'End': endDate
            },
            Granularity="MONTHLY",
            Filter={
                "And": [
                    {
                        "Not": {
                            "Dimensions": {
                                "Key": "RECORD_TYPE",
                                "Values": ["Credit", "Refund"]
                            }
                        }
                    }, {
                        "Dimensions": {
                            "Key": "SERVICE",
                            "Values": ["Amazon Simple Storage Service"]
                        }
                    }, {
                        "Dimensions": {
                            "Key": "LINKED_ACCOUNT",
                            "Values": accountIds
                        }
                    }]
            },
            Metrics=["UsageQuantity", "BlendedCost"],
            GroupBy=[
                {
                    'Type': 'DIMENSION',
                    'Key': "USAGE_TYPE"
                }
            ]
        )

        # The dictionary we are returning
        returnDict = {}

        assert len(result["ResultsByTime"]) == 1
        timeRange = result["ResultsByTime"][-1]

        for group in timeRange["Groups"]:
            # Parse out values
            usageType = group["Keys"][0]
            usageUnit = group["Metrics"]["UsageQuantity"]["Unit"]
            usageAmount = float(group["Metrics"]["UsageQuantity"]["Amount"])
            usageCost = float(group["Metrics"]["BlendedCost"]["Amount"])

            # We only care about how GBs are flowing in/out and stored in S3 buckets
            if "GB-Month" in usageUnit:
                assert usageType not in returnDict
                returnDict[usageType] = {"usageCost": usageCost, "usageAmount": usageAmount, "usageUnit": usageUnit}

        return returnDict

    def generateUserCostSummary(self, resourceSummaryMonthlyUnsorted, accounts):

        # Aggregate costs on a per-user basis
        userCostSummary = {}
        for resource in resourceSummaryMonthlyUnsorted.values():

            if resource.get_account_name() not in accounts.values():
                continue

            # Determine if the resource has a singular owner, is shared, or is un-owned
            resourceOwner = resource.get_email() if resource.get_email() is not None else (
                "Shared" if resource.is_shared else "Unowned")
            userCostSummary.setdefault(resourceOwner, {})
            userCostSummary[resourceOwner].setdefault(resource.get_resource_type(), 0)
            userCostSummary[resourceOwner][resource.get_resource_type()] += resource.get_monthly_cost()

        # Cleanup the data
        users = list(userCostSummary)
        for user in users:
            userServices = list(userCostSummary[user])
            for service in userServices:
                # Remove all services that the user paid less than $1 for
                if userCostSummary[user][service] < 1:
                    userCostSummary[user].pop(service, None)

            # If the user has no remaining services, remove the user from the list
            if len(userCostSummary[user].items()) == 0:
                userCostSummary.pop(user, None)

        # Get up to the top 10 services for each user
        for user in userCostSummary:
            n = min(len(userCostSummary[user].items()), 10)
            cost_list = sorted(userCostSummary[user].items(), key=lambda x: x[1], reverse=True)[:n]
            total_cost = sum([cost for (service, cost) in cost_list])
            cost_list.append(("Total", total_cost))
            userCostSummary[user] = dict(cost_list)

        return userCostSummary

    def saveUsageData(self, date):
        rows = []
        for day in self.daysOfMonthUpToAndIncluding(date):
            result = self.generateAccountSummary(self.accounts, day, day + datetime.timedelta(1))
            rows += [{"date": day, "amount-billed": sum(result[account].values()), "linked-account": account} for account in result.keys()]
        self.saveFile(self.generateBillingCsvFileName(date), self.toCsv(rows))

    def generateBetterReport(self) -> str:
        # Get date variables. We will be making the report for the previous day.
        yesterday = datetime.date.today() - datetime.timedelta(1)
        firstDayOfMonth = self.firstDayOfMonth(yesterday)
        lastDayOfMonth = self.lastDayOfMonth(yesterday)

        # Save usage data
        self.saveUsageData(yesterday)

        # Get a monthly and daily aggregation of costs. These reports are a nested dictionary in the form:
        # dictionary {account1: {service1: cost1, service2: cost2, ...}, account2: ...}
        accountSummaryMonthly = self.generateAccountSummary(self.accounts, firstDayOfMonth, lastDayOfMonth)
        accountSummaryDaily = self.generateAccountSummary(self.accounts, yesterday, yesterday + datetime.timedelta(1))

        usageTypeSummaryMonthly = self.generateUsageTypeSummary(self.compliance["accounts"], firstDayOfMonth,
                                                                lastDayOfMonth)
        s3StorageSummaryMonthly = self.generateS3StorageSummary(self.compliance["accounts"], firstDayOfMonth,
                                                                lastDayOfMonth)

        # Generate a summary on individual resources. This requires downloading the billing CSV
        resourceSummaryMonthlyUnsorted = self.generateResourceSummary(self.compliance["accounts"])
        resourceSummaryMonthly = dict(
            sorted(resourceSummaryMonthlyUnsorted.items(), key=lambda x: x[1].monthly_cost, reverse=True)[:30])
        userCostSummaryMonthly = self.generateUserCostSummary(resourceSummaryMonthlyUnsorted,
                                                              self.compliance["accounts"])
        totalUserCostMonthly = sum([user_costs['Total'] for (user, user_costs) in userCostSummaryMonthly.items()])

        # This will generate personalized compliance emails for everyone with a tagged resource
        self.generateComplianceSummary(yesterday)

        # Create a list of managed accounts
        managedAccounts = [self.compliance["accounts"][k] for k in self.compliance["accounts"]]

        # Create some simple aggregations, convert the strings sent over by AWS to floats
        totalsByAccountMonthly = {k: sum(accountSummaryMonthly[k].values()) for k in accountSummaryMonthly}
        totalsByAccountDaily = {k: sum(accountSummaryDaily[k].values()) for k in accountSummaryDaily}
        totalsByServiceMonthly = {k: sum(usageTypeSummaryMonthly[k].values()) for k in usageTypeSummaryMonthly}

        # Group accounts by managed and unmanaged
        totalsByManagedAccountMonthly = {k: totalsByAccountMonthly[k] for k in totalsByAccountMonthly if
                                         k in managedAccounts}
        totalsByManagedAccountDaily = {k: totalsByAccountDaily[k] for k in totalsByAccountDaily if k in managedAccounts}
        totalsByUnmanagedAccountMonthly = {k: totalsByAccountMonthly[k] for k in totalsByAccountMonthly if
                                           k not in managedAccounts}
        totalsByUnmanagedAccountDaily = {k: totalsByAccountDaily[k] for k in totalsByAccountDaily if
                                         k not in managedAccounts}

        # Render the email using Jinja
        return self.render_email(
            yesterday,
            self.email_recipients,
            accountTotalsMonthly=totalsByAccountMonthly,
            accountTotalsDaily=totalsByAccountDaily,
            serviceTotalsMonthly=totalsByServiceMonthly,
            serviceUsageTypesMonthly=usageTypeSummaryMonthly,
            accountServicesMonthly=accountSummaryMonthly,
            accountServicesDaily=accountSummaryDaily,
            resourceSummaryMonthly=resourceSummaryMonthly,
            s3StorageSummaryMonthly=s3StorageSummaryMonthly,
            userCostSummaryMonthly=userCostSummaryMonthly,
            totalUserCostMonthly=totalUserCostMonthly,
            totalsByManagedAccountMonthly=totalsByManagedAccountMonthly,
            totalsByManagedAccountDaily=totalsByManagedAccountDaily,
            totalsByUnmanagedAccountMonthly=totalsByUnmanagedAccountMonthly,
            totalsByUnmanagedAccountDaily=totalsByUnmanagedAccountDaily
        )


class GCPReport(Report):

    def __init__(self, config_path: str, date: datetime.date):
        super().__init__(platform='gcp', config_path=config_path, date=date)

    def readTerraWorkspaces(self, path: str) -> Mapping:
        try:
            if path is not None:
                infos = json.loads(Path(path).read_text())
                if not isinstance(infos, list):
                    return {}
                workspaces = [info['workspace'] for info in infos]
                return {workspace['googleProject']: workspace for workspace in workspaces}
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def addCreatedByToRows(self, rows: Sequence[Mapping], terra_workspaces: Mapping):
        for row in rows:
            id = row['id']
            row['created_by'] = terra_workspaces[id]['createdBy'] if id in terra_workspaces and 'createdBy' in terra_workspaces[id] else 'Unowned'

    def saveUsageData(self, date: datetime.date):
        rows = []
        for day in self.daysOfMonthUpToAndIncluding(date):
            results = group_by(self.doQuery(day), 'id', 'name', 'cost_today')
            rows += [
                {"date": day, "amount-billed": cost, "project-id": id, "project-name": name}
                for (id, name, cost) in results if cost > 0
            ]
        self.saveFile(self.generateBillingCsvFileName(date), self.toCsv(rows))

    def doQuery(self, date: datetime.date):
        terra_workspaces = self.readTerraWorkspaces(self.terra_workspaces_path)
        client = bigquery.Client()
        query_month = date.strftime('%Y%m')
        query_today = date.strftime('%Y-%m-%d')

        # noinspection SqlNoDataSourceInspection
        query = f'''SELECT
              project.name,
              service.description,
              SUM(CASE WHEN DATE(usage_start_time) <= '{query_today}' THEN cost + IFNULL(creds.amount, 0) ELSE 0 END) AS cost_month,
              SUM(CASE WHEN DATE(usage_start_time)  = '{query_today}' THEN cost + IFNULL(creds.amount, 0) ELSE 0 END) AS cost_today,
              project.id
            FROM `{self.bigquery_table}`
            LEFT JOIN UNNEST(credits) AS creds
            WHERE invoice.month = '{query_month}'
            GROUP BY project.name, service.description, project.id
            ORDER BY LOWER(project.name) ASC, service.description ASC, LOWER(project.id) ASC'''
        query_job = client.query(query)
        rows = list(query_job.result())
        rows = [dict(row) for row in rows]
        self.addCreatedByToRows(rows, terra_workspaces)
        return rows

    def generateBetterReport(self) -> str:
        self.saveUsageData(self.date)
        return self.render_email(self.date, self.email_recipients, rows=self.doQuery(self.date), cost_cutoff=self.cost_cutoff())

    def cost_cutoff(self) -> float:
        # cost cutoff is $1 on all days but friday, when it effectively does not exist
        return float('-inf') if self.date.weekday() == 4 else 1.0


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
    ...     {'foo': 2, 'bar': 2, 'baz': 1},
    ...     {'foo': 1, 'bar': 3, 'baz': 2},
    ... ]

    >>> list(group_by(my_rows, 'foo', 'bar'))
    [(1, 5), (2, 2)]

    >>> list(group_by(my_rows, 'foo', 'bar', 'baz'))
    [(1, 5, 5), (2, 2, 1)]

    >>> list(group_by(my_rows, 'foo', 'bar', 'baz', baz=2))
    [(1, 3, 2)]

    """
    sorted = sort_by(rows, key=key, reverse=False)
    grouped = (
        (k, list(v))
        for k, v in itertools.groupby(filter_by(sorted, **conditions), key=operator.itemgetter(key))
    )
    return (
        (k, *(reduce(list(val[target] for val in vals)) for target in targets))
        for k, vals in grouped
    )


def reduce(values: Sequence):
    if isinstance(values[0], numbers.Number):
        return sum(values)
    else:
        return next((v for v in values if v is not None), None)


def has_key(value, key):
    try:
        return value[key] is not None
    except KeyError:
        return False


def normalize_key(key):
    return key.lower() if isinstance(key, str) else key


def sort_by(rows: Iterable, key, reverse=True) -> Iterable:
    """
    >>> my_rows = [
    ...     {'bar': 1},
    ...     {'foo': 3, 'bar': 0},
    ...     {'foo': 1, 'bar': 3},
    ...     {'foo': 2, 'bar': 2}
    ... ]

    >>> list(sort_by(my_rows, 'bar'))
    [{'foo': 1, 'bar': 3}, {'foo': 2, 'bar': 2}, {'bar': 1}, {'foo': 3, 'bar': 0}]

    >>> list(sort_by(my_rows, 'foo', reverse=False))
    [{'foo': 1, 'bar': 3}, {'foo': 2, 'bar': 2}, {'foo': 3, 'bar': 0}, {'bar': 1}]
    """
    rows_with_keys = [row for row in rows if has_key(row, key)]
    rows_without_keys = [row for row in rows if not has_key(row, key)]
    return sorted(rows_with_keys, key=lambda row: normalize_key(row[key]), reverse=reverse) + rows_without_keys


def to_id(value: str) -> str:
    """
    >>> to_id('abc123')
    'abc123'

    >>> to_id('.ABC 1-2-3!')
    '-ABC-1-2-3-'

    >>> to_id(None)
    'None'

    >>> to_id(123)
    '123'
    """
    return re.sub('[^a-zA-Z0-9]', '-', str(value))


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
                        default=(datetime.datetime.now() - datetime.timedelta(days=1)).strftime(date_format),
                        nargs='?',
                        help='YYYY-MM-DD to generate a report for. Defaults to yesterday.')
    parser.add_argument('--config',
                        default=Path.cwd() / 'config.json',
                        help='Path to config.json. Default to current directory.')
    parser.add_argument('--terra-workspaces',
                        default=None,
                        help='Path to json file containing Terra workspace information.')
    arguments = parser.parse_args()

    if arguments.report_type == "gcp":
        arguments.report_date = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime(date_format)

    date = datetime.datetime.strptime(arguments.report_date, date_format).date()
    report = report_types[arguments.report_type](arguments.config, date)
    print(report.generateBetterReport())
