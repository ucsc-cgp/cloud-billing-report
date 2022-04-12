class CostPacket:
    def __init__(self, dailyCost=0, monthlyCost=0):
        self.dailyCost = dailyCost
        self.monthlyCost = monthlyCost
        
    def addDailyCost(self, amount: 'String'):
        assert float(amount) >= 0
        self.dailyCost += float(amount)
        
    def addMonthlyCost(self, amount: 'String'):
        assert float(amount) >= 0
        self.monthlyCost += float(amount)
        
    def getDailyCost(self):
        return self.dailyCost
    
    def getMonthlyCost(self):
        return self.monthlyCost