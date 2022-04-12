import src.gcp.downloadGcpResourceReport as downloadGcpResourceReport
from src.gcp.gcpAggregator import GcpAggregator
from src.utils.emailBuilder import EmailBuilder
import os

class GcpReportGenerator:

    def __init__(self, config, date):
        self.config = config
        self.date = date

    def loadGcpResources(self):
        return downloadGcpResourceReport.downloadGcpBillingRows(self.config.gcpBucket, self.date)

    def createAggregator(self, resourceList):
        return GcpAggregator(resourceList)

    def createBulkEmail(self, aggregator, gcpResources, writeDir):

        accountSummary = aggregator.aggregateByAccount(gcpResources)
        accountServiceSummary = {acc: aggregator.aggregateByService(accountSummary[acc]) for acc in accountSummary}

        eb = EmailBuilder()
        emailStr = eb.renderGcpEmail(self.date, self.config.gcpEmailSender, self.config.gcpEmailRecipients,
                                     allResources=gcpResources,
                                     accountServiceSummary=accountServiceSummary,
                                     accountSummary=accountSummary)

        with open(os.path.join(writeDir, "gcpReport.eml"), "w") as emlFile:
            emlFile.write(emailStr)



