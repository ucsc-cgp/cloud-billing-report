class report_resource:

    def __init__(self, resource_arn: str, resource_type: str, account_id: str, account_name: str, region: str):
        self.resource_arn = resource_arn
        self.resource_type = resource_type
        self.account_id = account_id
        self.account_name = account_name
        self.region = region
        self.compliance_status = None
        self.tag_status = {
            "Owner": None,
            "owner": None,
            "noncompliant-maid-service": None
        }
        self.email = None
        self.is_shared = False

        self.daily_cost = 0
        self.monthly_cost = 0

        self.url = None

    # sets the resource url if possible, otherwise just links to the dashboard
    def set_resource_url(self):
        if self.resource_type == "Amazon Elastic Compute Cloud":
            self.url = f"https://console.aws.amazon.com/ec2/v2/home?region={self.region}#InstanceDetails:instanceId={self.resource_arn}"
        elif self.resource_type == "Amazon Simple Storage Service":
            self.url = f"https://s3.console.aws.amazon.com/s3/buckets/{self.resource_arn}?region={self.region}&tab=objects"
        elif self.resource_type == "Amazon Elasticsearch Service":
            self.url = f"https://console.aws.amazon.com/es/home?region={self.region}#"
        else:
            self.url = f"https://console.aws.amazon.com/console/home?region={self.region}"

    # simple matching between this resource object and a billing report CSV row
    def is_match(self, account_id: str, resource_arn: str):
        return self.account_id == account_id and self.resource_arn == resource_arn

    # Set the compliance status of this resource. If no value is provided, calculate the compliance status based on
    # other resource properties.
    def set_compliance_status(self, compliance_status=None):
        if compliance_status is not None:
            self.compliance_status = compliance_status
        elif self.tag_status["noncompliant-maid-service"] is not None:
            self.compliance_status = "NON_COMPLIANT"
        else:
            self.compliance_status = "COMPLIANT"

    # Add a resource tag to the list of tags of this resource
    def add_tag_value(self, tag: str, tag_value: str):
        assert tag in self.tag_status

        self.tag_status[tag] = tag_value
        if tag == "Owner" or tag == "owner":
            self.set_email_if_valid(tag_value)

    # Set the email property if the provided tag value looks like an email address
    def set_email_if_valid(self, tag_value: str):
        if tag_value is None:
            return
        elif tag_value == 'cluster-admin@soe.ucsc.edu':  # route all cluster admin emails to erich
            self.email = 'weiler@soe.ucsc.edu'
        elif tag_value.partition("@")[2].find(".") != -1:  # check if the tag 'looks' like an email
            self.email = tag_value
        elif "shared" in tag_value.lower():
            self.is_shared = True

    def set_daily_cost(self, val: float):
        # if the daily cost is already set, we shouldn't be setting it again
        assert self.daily_cost == 0
        self.daily_cost = val

    # Since the monthly cost is an aggregate of multiple days, add every value passed
    def add_to_monthly_cost(self, val: float):
        self.monthly_cost += val

    def get_resource_arn(self):
        return self.resource_arn

    def get_resource_type(self):
        return self.resource_type

    def get_account_id(self):
        return self.account_id

    def get_account_name(self):
        return self.account_name

    def get_region(self):
        return self.region

    def get_compliance_status(self):
        return self.compliance_status

    def get_tag_status(self):
        return self.tag_status

    def get_email(self):
        return self.email

    def get_daily_cost(self):
        return self.daily_cost

    def get_monthly_cost(self):
        return self.monthly_cost
