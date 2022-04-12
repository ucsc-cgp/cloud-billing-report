from src.aws.awsResource import AwsResource
from src.utils.config import Config
import src.aws.downloadAwsBillingCsv
import boto3
import datetime
from dateutil import relativedelta
import uuid

class AwsResourceAggregator:
    
    def __init__(self, billingReport: 'DictReader', yesterday: 'datetime.date'):
        self.billingReport = billingReport
        
        # All line items in the billing report are assumed to be in the proper month, so we only care about the daily
        # range
        self.dailyCostDates = (yesterday, yesterday + relativedelta.relativedelta(days=1))
        
        # Dictionary of resources where the key is the resource ID and the value is an awsResource object
        self.allResourcesDict = {}
        self.allResourcesList = []
        self.createResourcesDict()
        
    def getAllResources(self):
        return self.allResourcesList
        
    def createResourcesDict(self):
        for row in self.billingReport:
                
            # Skip credits and refunds
            if row[Config.LINE_ITEM_TYPE] in Config.LINE_ITEM_TYPE_SKIP:
                continue
            
            # The logical ID we'll be using for the resource
            logicalId = row[Config.RESOURCE_ID]
            
            # If we don't have the resource already logged, create it now
            if logicalId not in self.allResourcesDict:
                
                # If the line item is not associated with a resource, then skip it
                if logicalId == None or len(logicalId) == 0:
                    logicalId = "NA"+uuid.uuid4().hex
                
                # Create the resource object
                resource = AwsResource(logicalId, 
                                   row[Config.SERVICE_TYPE], 
                                   row[Config.ACCOUNT_ID], 
                                   row[Config.RESOURCE_REGION])
            
                # Add the owner tag values if present
                for ownerTag in Config.OWNER_TAGS:
                    resource.setTag(row[ownerTag])
                    
                # Add the resource to the dictionary
                self.allResourcesDict[logicalId] = resource
                
            # Get the billing dates for this row
            billingStartDate = datetime.datetime.strptime(row[Config.BILLING_START_DATE],"%Y-%m-%dT%H:%M:%SZ").date()
            billingItemEndDate = datetime.datetime.strptime(row[Config.BILLING_END_DATE],"%Y-%m-%dT%H:%M:%SZ").date()
            
            dailyCost = 0
            if billingStartDate >= self.dailyCostDates[0] and billingItemEndDate <= self.dailyCostDates[0]:
                dailyCost = row[Config.LINE_ITEM_COST]
                    
            # TODO: ADD DAILY COST LOGIC
            self.allResourcesDict[logicalId].addUsageType(row[Config.USAGE_TYPE], 
                                                                        dailyCost, 
                                                                        row[Config.LINE_ITEM_COST])
           
        # Convert to a list of resources for easier handling
        self.allResourcesList = self.allResourcesDict.values()
        
    def aggregateByAccount(self, resourceList):
        
        # Get each account
        accountIds = set([r.getAccountId() for r in resourceList])
        
        # Create a dictionary with the top level key being an AWS account
        accounts = {accountId: [] for accountId in accountIds}
        
        # Add each resource under its respective account
        for r in resourceList:
            accounts[r.getAccountId()].append(r)
            
        return accounts
    
    def aggregateByService(self, resourceList):
        
        # Get each service type
        serviceTypes = set([r.getServiceType() for r in resourceList])
        
        # Create a dictionary with the top level key being an AWS service type
        services = {serviceType: [] for serviceType in serviceTypes}
        
        # Add each resource under its respective service
        for r in resourceList:
            services[r.getServiceType()].append(r)
            
        return services
    
    def aggregateByOwner(self, resourceList):
        
        # Get each owner
        owner = set([r.getOwner() for r in resourceList])
        
        # Create a dictionary with the top level key being an owner
        owners = {o: [] for o in owner}
        
        # Add each resource under its respective owner
        for r in resourceList:
            owners[r.getOwner()].append(r)
            
        return owners
    
    def aggregateByResourceId(self, resourceList):
        
        # Resources are already aggregated by ID, just convert it into the properform
        return {resource.getResourceId(): [resource] for resource in resourceList}
    
    def aggregateByUsageType(self, resourceList):
        
        usageTypes = []
        
        # Usage Types are on an individual resource basis
        for resource in resourceList:
            usageTypes += list(resource.getUsageTypes().keys())
            
        usageTypes = {ut: [] for ut in set(usageTypes)}
        
        for r in resourceList:
            for usageType in r.getUsageTypes().keys():
                usageTypes[usageType].append(r.createResourceCopyWithOneUsageType(usageType))
                
        return usageTypes
    
    def sumDailyCosts(self, resourceList):
        return sum([r.sumDailyUsageCost() for r in resourceList])
    
    def sumMonthlyCosts(self, resourceList):
        return sum([r.sumMonthlyUsageCost() for r in resourceList])

