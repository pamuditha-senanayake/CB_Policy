from river.drift import ADWIN, PageHinkley

class DriftDetector:
    def __init__(self, method="ADWIN"):
        self.method = method
        if method == "ADWIN":
            self.detector = ADWIN()
        elif method == "ADWIN_delta_0.05":
            self.detector = ADWIN(delta=0.05)
        else:
            self.detector = PageHinkley()
            
    def add_element(self, value):
        self.detector.update(value)
        return self.detector.drift_detected
