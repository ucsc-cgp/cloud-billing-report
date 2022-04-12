from src.aws.awsAggregator import AwsResourceAggregator
from src.utils.costPacket import CostPacket
from src.utils.emailBuilder import EmailBuilder
from src.utils.config import Config
import src.aws.downloadAwsBillingCsv as downloadAwsBillingCsv
from dateutil import relativedelta
import boto3
import datetime
import os
import uuid

class AwsReportGenerator:
    
    TOTAL_KEY = "Total"
    
    def __init__(self, config: "Config", date: 'datetime.date'):
        self.config = config
        self.date = date
    
    def downloadReport(self):
        # Create an S3 Client
        s3 = boto3.client(Config.AWS_S3_CLIENT,
                          aws_access_key_id=self.config.awsAccessKey,
                          aws_secret_access_key=self.config.awsSecretKey)

        # Create the path to the manifest file within the billing S3 bucket
        objectPath = downloadAwsBillingCsv.createAwsBillingManifestObjectPath(self.config.awsReportPrefix, 
                                                                              self.date)

        # Download the CSV file locally
        csvGzipFilePath = downloadAwsBillingCsv.downloadAwsBillingCsv(s3, self.config.awsS3Bucket, objectPath, Config.DATA_DIR, Config.MANIFEST_FILE, Config.CSV_FILE)

        return csvGzipFilePath
    
    def loadReport(self, csvGzipFilePath):
        # Read the CSV file into a DictReader
        billingReport = list(downloadAwsBillingCsv.readInCsv(csvGzipFilePath))
        return billingReport
    
    def createAggregator(self, billingReport):
        # Create an aggregator based on the billing report
        agg = AwsResourceAggregator(billingReport, self.date)
        return agg
    
    def splitResourcesByManagedAndUnmanaged(self, 
                                            resourceList: '[AwsResource]'):
        
        # We will return two dictionaries of the same form as resourceDict
        managedResources = []
        unmanagedResources = []
        
        for resource in resourceList:
            if resource.getAccountId() in self.config.awsManagedAccounts.keys():
                managedResources.append(resource)
            else:
                unmanagedResources.append(resource)
        
        return managedResources, unmanagedResources
    
    def recursiveAggregator(self, 
                            aggregator: "AwsResourceAggregator", 
                            aggregationOrder: "[String]", 
                            resourceList: "[AwsResource]", 
                            addTotal=False,
                            threshold=0):
        
        # The aggregationOrder parameter is a list of strings that map to each of the below functions
        aggMethods = {"account"  : aggregator.aggregateByAccount, 
                      "service"  : aggregator.aggregateByService,
                      "owner"    : aggregator.aggregateByOwner,
                      "resource" : aggregator.aggregateByResourceId,
                      "usage"    : aggregator.aggregateByUsageType}
        currentAggregationMethod = aggMethods[aggregationOrder.pop(0)]
        summary = currentAggregationMethod(resourceList)
        
        # If this was our final aggregation, calculate the cost packets and then return
        if len(aggregationOrder) == 0:
            
            # Keep track of total costs
            dailyTotal = 0
            monthlyTotal = 0
            
            # Calculate the cost packets for each resource at this level of the aggregation
            for k in summary:
                
                # Resource daily and monthly costs
                dailyCost = int(aggregator.sumDailyCosts(summary[k]))
                monthlyCost = int(aggregator.sumMonthlyCosts(summary[k]))
                
                # Summed daily and monthly costs for this aggregation
                dailyTotal += dailyCost
                monthlyTotal += monthlyCost
                
                # Add cost packet
                summary[k] = CostPacket(dailyCost, monthlyCost)
                
            # Sort the dictionary
            summary = {key: costPacket for key, costPacket in sorted(summary.items(), 
                                                                     key=lambda item: item[1].monthlyCost, 
                                                                     reverse=True) if costPacket.monthlyCost >= threshold}
        
            # Add a totals after the sorting
            if addTotal:
                summary[AwsReportGenerator.TOTAL_KEY] = CostPacket(dailyTotal, monthlyTotal)
                
            return summary
        
        # More aggregations still need to be performed
        for k in summary:
            summary[k] = self.recursiveAggregator(aggregator, aggregationOrder.copy(), summary[k], addTotal, threshold)
            
        return summary
    
    def createBulkEmail(self, aggregator, managedResources, unmanagedResources, writeDir):
        
        # Create the top-level summary for monthly/daily costs by account
        managedAccountSum = self.recursiveAggregator(aggregator, ["account"], managedResources, addTotal=False)
        unmanagedAccountSum = self.recursiveAggregator(aggregator, ["account"], unmanagedResources, addTotal=False)

        # All account summary by service
        accountServiceSum = self.recursiveAggregator(aggregator, ["account", "service"], aggregator.getAllResources(), addTotal=True)

        # Service cost summary
        serviceSum = self.recursiveAggregator(aggregator, ["service"], managedResources, addTotal=False, threshold=1)

        # Create the summary for user expenditure
        ownerServiceSum = self.recursiveAggregator(aggregator, ["owner", "service"], managedResources, addTotal=True, threshold=1)
        ownerServiceSum = {o: s for o, s in ownerServiceSum.items() if s[AwsReportGenerator.TOTAL_KEY].monthlyCost > 1}

        resourceUsageSum = self.recursiveAggregator(aggregator, ["resource", "usage"], managedResources, addTotal=True, threshold=1)
        resourceUsageSum = {r: ut for r, ut in resourceUsageSum.items() if ut[AwsReportGenerator.TOTAL_KEY].monthlyCost > 20}

        # Top service usage report
        serviceUsageSum = self.recursiveAggregator(aggregator, ["service", "usage"], managedResources, addTotal=True, threshold=1)
        serviceUsageSum = {s: ut for s, ut in sorted(serviceUsageSum.items(), reverse=True, key=lambda item: item[1][AwsReportGenerator.TOTAL_KEY].monthlyCost)[:3]}
        
        eb = EmailBuilder()
        emailStr = eb.renderAwsEmail(self.date, self.config.awsEmailSender, self.config.awsEmailRecipients, individual=False,
                             allAccounts=self.config.awsAllAccounts,
                             allResourcesDict=aggregator.allResourcesDict,
                             accountServiceSum=accountServiceSum,
                             serviceSum=serviceSum,
                             managedAccountSum=managedAccountSum,
                             unmanagedAccountSum=unmanagedAccountSum,
                             ownerServiceSum=ownerServiceSum,
                             resourceUsageSum=resourceUsageSum,
                             serviceUsageSum=serviceUsageSum)
        
        with open(os.path.join(writeDir, "awsReport.eml"), "w") as emlFile:
            emlFile.write(emailStr)
            
    def createIndividualEmails(self, aggregator, managedResources, writeDir):
        ownersAgg = self.recursiveAggregator(aggregator, ["owner", "account", "resource"], managedResources, addTotal=False)
        
        # For each owner, create an email
        for owner in ownersAgg:
            
            if owner is None or "@" not in owner:
                continue
                
            eb = EmailBuilder()
            emailStr = eb.renderAwsEmail(self.date, self.config.awsEmailSender, [owner], individual=True,
                                 allAccounts=self.config.awsAllAccounts,
                                 ownerSummary=ownersAgg[owner])
            
            # Write the email to the provided directory based on the owner email
            with open(os.path.join(writeDir, owner.split("@")[0] + uuid.uuid4().hex +  ".eml"), "w") as emlFile:
                emlFile.write(emailStr)
            

