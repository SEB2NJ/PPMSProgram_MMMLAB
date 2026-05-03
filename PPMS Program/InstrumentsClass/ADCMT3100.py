import pyvisa
import time

class ADCMT3100:
    def __init__(self, resource_name = "GPIB1::20::INSTR"):
        self.Visa = pyvisa.ResourceManager().open_resource(resource_name)
        self.Visa.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, traceback):
        # print("ExitFunction_ADCMT3100 Run")
        pass
        
    def initialize(self):
        self.Visa.write("MD0")
        self.Visa.write("RLN 2,0,1")

    def ch_close(self, args):
        command = " "
        text = ""
        for arg in args:
            command += f"C0{arg-1},"
            text += f"Ch{arg-1} "
        self.Visa.write(f"DI {command}G")
        
    def ch_open(self, args):
        command = " "
        text = ""
        for arg in args:
            command += f"O0{arg-1},"
            text += f"Ch{arg-1} "
        self.Visa.write(f"DI {command}G")
        
    def ch_fullopen(self):
        self.Visa.write("OS 2,0")
        
if __name__ == "__main__":
    
    ADC3100 = ADCMT3100()
    ADC3100.initialize()
    ADC3100.ch_close([5,10])
    time.sleep(2)
    ADC3100.ch_open([5])
    time.sleep(2)
    ADC3100.ch_fullopen()