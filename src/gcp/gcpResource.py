
class GcpResource:

    def __init__(self, accountName, serviceName, costPacket):
        self.accountName = accountName
        self.serviceName = serviceName
        self.costPacket = costPacket

    def getAccountName(self):
        return self.accountName

    def getServiceName(self):
        return self.serviceName

    def getCostPacket(self):
        return self.costPacket
