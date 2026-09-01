class DriftDetector:
    def __init__(self):
        self.window = []
        self.state = 1.0
        
    def add_element(self, value):
        self.window.append(value)
        if len(self.window) > 30:
            self.window.pop(0)
            
        if len(self.window) == 30:
            avg = sum(self.window) / 30.0
            if self.state == 1.0 and avg < 0.7:
                self.state = 0.0
                return True
            elif self.state == 0.0 and avg >= 0.7:
                self.state = 1.0
                return True
        return False
