from src.gcp.gcpResource import GcpResource
from src.utils.costPacket import CostPacket

class GcpAggregator:

    GCP_ACCOUNT_NAME = 'name'
    GCP_USAGE_TYPE = 'description'
    GCP_MONTHLY_COST = 'cost_month'
    GCP_DAILY_COST = 'cost_today'

    def __init__(self, resourceList):
        self.resourceList = resourceList

    def createGcpResources(self):

        resources = []

        for row in self.resourceList:

            # Get the details we are interested in from the list
            accountName = row[GcpAggregator.GCP_ACCOUNT_NAME]
            if accountName is None or len(accountName) == 0:
                continue

            usageType = row[GcpAggregator.GCP_USAGE_TYPE]
            monthlyCost = int(row[GcpAggregator.GCP_MONTHLY_COST])
            dailyCost = int(row[GcpAggregator.GCP_DAILY_COST])

            # Create a cost packet
            costPacket = CostPacket(dailyCost,monthlyCost)
            resources.append(GcpResource(accountName,usageType, costPacket))

        return resources

    def aggregateByAccount(self, gcpResources):

        accountSum = {}
        for resource in gcpResources:
            accountSum.setdefault(resource.getAccountName(), [])
            accountSum[resource.getAccountName()].append(resource)

        return accountSum

    def aggregateByService(self, gcpResources):

        accountSum = {}
        for resource in gcpResources:
            accountSum.setdefault(resource.getServiceName(), [])
            accountSum[resource.getServiceName()].append(resource)

        return accountSum
