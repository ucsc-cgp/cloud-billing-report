
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

    def add_owner_tag_value(self, tag: str, tag_value: str):

        # Tag must be 'Owner' or 'owner'
        assert tag in self.tag_status

        # Add the tag value to the dictionary. This value may not be an email address, it can be 'shared'.
        self.tag_status[tag] = tag_value

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
