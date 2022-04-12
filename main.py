from src.utils.config import Config
import datetime
import argparse

class Main:

    EMAIL_DIR = "/tmp/personalizedEmails/"
    
    def runAwsReport(self, config, date):
            
        # import the AWS report generator
        from src.aws.awsReportGenerator import AwsReportGenerator
        
        # Download and create the aggregator from scratch
        report = AwsReportGenerator(config, date)
        
        # Download the billing CSV and load it into a list
        csvGzipFilePath = report.downloadReport()
        billingReport   = report.loadReport(csvGzipFilePath)

        # Aggregate the data into AWS resource objects
        aggregator      = report.createAggregator(billingReport)
        
        # Split resources based on whether or not they are in managed or unmanaged accounts
        managedResources, unmanagedResources = report.splitResourcesByManagedAndUnmanaged(aggregator.getAllResources())
        
        # Create the bulk and individual emails
        report.createBulkEmail(aggregator, managedResources, unmanagedResources, Main.EMAIL_DIR)
        report.createIndividualEmails(aggregator, managedResources, Main.EMAIL_DIR)

    def runGcpReport(self, config, date):

        # import the GCP report generator
        from src.gcp.gcpReportGenerator import GcpReportGenerator

        # Create the report generator object
        report = GcpReportGenerator(config, date)

        # Load the billing details into a list
        resourceList = report.loadGcpResources()
        aggregator = report.createAggregator(resourceList)

        # create aggregator
        gcpSummary = aggregator.createGcpResources()

        # Create the bulk email
        report.createBulkEmail(aggregator, gcpSummary, Main.EMAIL_DIR)

if __name__ == '__main__':

    # Parse input arguments
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('reportType', type=str, help='The type of report (aws or gcp)')
    args = parser.parse_args()

    # Create the runner and load our config file
    runner = Main()
    config = Config("/config.json")

    if args.reportType == 'aws':
        # Run the AWS report
        runner.runAwsReport(config, datetime.date.today() - datetime.timedelta(days=1))
    elif args.reportType == 'gcp':
        # Run the GCP report
        runner.runGcpReport(config, datetime.date.today() - datetime.timedelta(days=1))
    else:
        print("Unrecognized input argument. Please pass 'aws' or 'gcp'")
