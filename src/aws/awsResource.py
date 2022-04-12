from src.utils.config import Config
from src.utils.costPacket import CostPacket

class AwsResource:
    
    def __init__(self, 
                 resourceId: 'String',
                 serviceType: 'String',
                 accountId: 'String',
                 awsRegion: 'String'):
        
        self.resourceId = self.setResourceId(resourceId)
        self.serviceType = serviceType
        self.accountId = accountId
        self.awsRegion = awsRegion
        
        # Each service can have multiple different usage types. {'usageType': CostPacket}.
        self.usageTypes = {}
        
        self.owner = None
        
    def getResourceId(self):
        return self.resourceId
    
    def getServiceType(self):
        return self.serviceType
    
    def getAccountId(self):
        return self.accountId
    
    def getAwsRegion(self):
        return self.awsRegion
    
    def getUsageTypes(self):
        return self.usageTypes
    
    def getOwner(self):
        return self.owner
        
    def setTag(self, tagValue):
        if tagValue is not None and len(tagValue) > 0:
            self.owner = tagValue
        
    def setResourceId(self, resourceId):
        if resourceId == None or len(resourceId) == 0:
            return "-"
        else:
            return resourceId
            
    def addUsageType(self, usageTypeName, dailyCost, monthlyCost):
        # Create a cost packet for this usage type if it isn't already part of the resource
        if usageTypeName not in self.usageTypes:
            self.usageTypes[usageTypeName] = CostPacket()
            
        # increment the daily and monthly cost values
        self.usageTypes[usageTypeName].addDailyCost(dailyCost)
        self.usageTypes[usageTypeName].addMonthlyCost(monthlyCost)
        
    def createResourceCopyWithOneUsageType(self, usageType: 'String'):
        
        # Create a copy of the resource that is the same as the parent resource in terms of constructor parameters
        newResource = AwsResource(self.resourceId, self.serviceType, self.accountId, self.awsRegion)
        
        # The new resource will only be associated with a singular usage type. This is used for aggregations
        currentUsageCostPacket = self.getUsageTypes()[usageType]
        newResource.addUsageType(usageType, currentUsageCostPacket.dailyCost, currentUsageCostPacket.monthlyCost)
        
        return newResource
        
    def sumMonthlyUsageCost(self):
        monthlyCost = 0
        for ut in self.usageTypes:
            monthlyCost += self.usageTypes[ut].getMonthlyCost()
        return monthlyCost
            
    def sumDailyUsageCost(self):
        dailyCost = 0
        for ut in self.usageTypes:
            dailyCost += self.usageTypes[ut].getDailyCost()
        return dailyCost
        
        