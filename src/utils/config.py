import json

class Config:
    
    # Config keys
    AWS_KEY = "aws"
    GCP_KEY = "gcp"
    
    # AWS Clients
    AWS_S3_CLIENT = 's3'

    # File Paths
    DATA_DIR      = "data/"
    EMAIL_DIR     = "/tmp/personalizedEmails"
    MANIFEST_FILE = "manifest.json"
    CSV_FILE      = "billingReport.csv"
    
    # Keys in the CSV file we are interested in
    ACCOUNT_ID            = "lineItem/UsageAccountId"
    SERVICE_TYPE          = "product/ProductName"
    USAGE_TYPE            = "product/usagetype"
    LINE_ITEM_TYPE        = "lineItem/LineItemType"
    LINE_ITEM_TYPE_SKIP   = ["credit","refund","SavingsPlanNegation"]
    LINE_ITEM_COST        = "lineItem/BlendedCost"
    LINE_ITEM_DESCRIPTION = "lineItem/LineItemDescription"
    RESOURCE_ID           = "lineItem/ResourceId"
    RESOURCE_REGION       = "product/region"
    
    # Billing date range
    BILLING_START_DATE = "lineItem/UsageStartDate"
    BILLING_END_DATE   = "lineItem/UsageEndDate"
    
    # Tags
    OWNER_TAGS      = ["resourceTags/user:Owner","resourceTags/user:owner"]
    COMPLIANCE_TAGS = ["resourceTags/user:noncompliant-maid-service"]
    
    # Jinja Templates
    AWS_REPORT_TEMPLATE = "awsReport.html"
    AWS_INDIVIDUAL_REPORT_TEMPLATE = "awsIndividualReport.html"
    GCP_REPORT_TEMPLATE = "gcpReport.html"
    
    
    def __init__(self, configPath):
        
        jsonConfig = None
        
        with open(configPath, "r") as configFile:
            # Load the configuration file into a JSON
            jsonConfig = json.load(configFile)
        
        # Get the configuration values for both AWS and GCP
        awsJson = jsonConfig[Config.AWS_KEY]
        gcpJson = jsonConfig[Config.GCP_KEY]
        
        # Credentials
        self.awsAccessKey    = awsJson['access_key']
        self.awsSecretKey    = awsJson['secret_key']
        self.awsS3Bucket     = awsJson['bucket']
        self.awsReportPrefix = awsJson['report_name']

        # AWS accounts, this is a dictionary {"accountId": "accountName"}
        self.awsAllAccounts = awsJson['accounts']

        # AWS managed accounts, this is a dictionary {"accountId": "accountName"}
        self.awsManagedAccounts = awsJson['compliance']['accounts']
        
        # who is sending the email and where they are going
        self.awsEmailSender = awsJson["from"]
        self.awsEmailRecipients = awsJson["recipients"]
        
        # Get the GCP big query bucket
        self.gcpBucket = gcpJson["bigquery_table"]
        
        # who is sending the email and where they are going
        self.gcpEmailSender = gcpJson["from"]
        self.gcpEmailRecipients = gcpJson["recipients"]
