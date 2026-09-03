from river.drift import ADWIN, PageHinkley

try:
    from river.drift import KSWIN
except:
    KSWIN = None

class DriftDetector:
    def __init__(self, method="ADWIN", **kwargs):
        self.method = method
        if method == "ADWIN":
            if "delta" in kwargs:
                self.detector = ADWIN(delta=kwargs["delta"])
            else:
                self.detector = ADWIN()
        elif method == "ADWIN_delta_0.1":
            self.detector = ADWIN(delta=0.1)
        elif method == "PageHinkley":
            self.detector = PageHinkley()
        elif method == "KSWIN":
            if KSWIN:
                self.detector = KSWIN()
            else:
                self.detector = PageHinkley()
        else:
            self.detector = PageHinkley()
            
    def add_element(self, value):
        self.detector.update(value)
        return self.detector.drift_detected
