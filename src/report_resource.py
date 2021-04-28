
class report_resource:

    def __init__(self, resource_id: str, resource_type: str, account_id:str, account_name: str, region: str, compliance_status: str):
        self.resource_id = resource_id
        self.resource_type = resource_type
        self.account_id = account_id
        self.account_name = account_name
        self.region = region
        self.compliance_status = compliance_status
        self.tag_status = {
            "Owner": None,
            "owner": None
        }
        self.email = None

        self.daily_cost = 0
        self.monthly_cost = 0

    # simple matching between this resource object and a billing report CSV row
    def is_match(self, account_id: str, resource_id: str):
        return self.account_id == account_id and self.resource_id == resource_id

    def add_owner_tag_value(self, tag: str, tag_value: str):

        # Tag must be 'Owner' or 'owner'
        assert tag in self.tag_status

        # Add the tag value to the dictionary. This value may not be an email address, it can be 'shared'.
        self.tag_status[tag] = tag_value
        self.set_email_if_valid(tag_value)

    def set_email_if_valid(self, tag_value: str):
        lowercase_tag = tag_value.lower()

        # If the compliant tag does not contain the word 'shared' then this is an email address
        if "shared" not in lowercase_tag:
            if tag_value == 'cluster-admin@soe.ucsc.edu':  # route all cluster admin emails to erich
                self.email = 'weiler@soe.ucsc.edu'
            else:
                self.email = tag_value

    def set_daily_cost(self, val: float):
        # if the daily cost is already set, we shouldn't be setting it again
        assert self.daily_cost == 0
        self.daily_cost = val

    # Since the monthly cost is an aggregate of multiple days, add every value passed
    def add_to_monthly_cost(self, val: float):
        self.monthly_cost += val

    def get_resource_id(self):
        return self.resource_id

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
