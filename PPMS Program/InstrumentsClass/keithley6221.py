import pyvisa
import time
import sys

class Keithley6221:
    def __init__(self, variableSet, resource_name = 'GPIB1::12::INSTR'):
        self.Visa = pyvisa.ResourceManager().open_resource(resource_name)
        self.variableSet = variableSet
        self.Visa.clear()

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, traceback):
        pass
        
    def safety(self, value):
        value *= 1e-3
        if value > 0.021:
            value = 1e-6
            self.status.update("Current Error(too high to pass current)")
            self.Visa.write(":SOUR:WAVE:ABOR")
            self.Visa.write(":OUTP OFF")
            sys.exit()       
            #raise ValueError("Current Error: too high to pass current")
        return value
        
    def dc_init(self):
        self.Visa.write("CLE")
        self.Visa.write(":SOUR:CURR:RANG:AUTO ON")
        self.Visa.write(":SOUR:CURR "+ str(self.safe_value))
        self.Visa.write(":SOUR:CURR:COMP 15")
        time.sleep(1)
        self.Visa.write(":OUTP ON")
        
    def ac_init(self, freq, ampl, offs, func):
        self.safe_value = self.safety(ampl)
        self.Visa.write(":SOUR:WAVE:ABOR")
        self.Visa.write(f":SOUR:WAVE:FREQ {freq}")  
        self.Visa.write(f":SOUR:WAVE:AMPL {self.safe_value}")
        print(self.safe_value)
        self.Visa.write(f":SOUR:WAVE:OFFS {offs}")
        self.Visa.write(f":SOUR:CURR:COMP {self.variableSet.kei6221ComplienceVoltage}")
        self.Visa.write(f":SOUR:WAVE:FUNC {func}")
        self.Visa.write(":SOUR:WAVE:PMAR:STAT ON")    
        self.Visa.write(":SOUR:WAVE:PMAR:OLIN 4")
        self.Visa.write(":SOUR:WAVE:RANG FIX") 
        time.sleep(1)
        self.Visa.write(":SOUR:WAVE:ARM")
        self.Visa.write(":SOUR:WAVE:INIT")
    
            
    def pulse_init(self):

        #self.Visa.write('SOUR:PDEL:NVPR 1')    
        self.Visa.write('SOUR:PDEL:LOW 0')                 #Sets pulse low value to 0mA.ok
        self.Visa.write('SOUR:PDEL:WIDT 1e-3')             #Sets pulse width to 1ms.
        self.Visa.write('SOUR:PDEL:SDEL 6e-4')           #Sets source delay パルスが入力されてから何秒後に測定するかを決める
        self.Visa.write('SOUR:PDEL:COUN 1')                #Sets pulse count to 1.
        self.Visa.write('SOUR:PDEL:RANG BEST')             #Selects the best source range.ok
        self.Visa.write('SOUR:PDEL:INT 5')                #Sets pulse interval to 10 PLC. 1回にかける時間。1で20ms
        self.Visa.write('SOUR:PDEL:SWE OFF')               #Disables sweep function.ok
        self.Visa.write('SOUR:PDEL:LME 2')                 #Set for two low pulse measurements.
        self.Visa.write("TRAC:FEED SENS1")
        self.Visa.write("TRAC:POIN 2")
        
        
    def set_ampl(self, value):
        self.safe_value = self.safety(value)
        self.Visa.write(":SOUR:WAVE:ABOR")
        self.Visa.write(":SOUR:WAVE:AMPL "+ str(self.safe_value))
        self.Visa.write(":SOUR:WAVE:ARM")
        self.Visa.write(":SOUR:WAVE:INIT")
        
    def set_freq(self, value):
        self.Visa.write(":SOUR:WAVE:ABOR")
        self.Visa.write(":SOUR:WAVE:ARM")
        self.Visa.write(f":SOUR:WAVE:FREQ {value}") 
        self.Visa.write(":SOUR:WAVE:INIT")
        
    def set_offs(self, value):
        self.safe_value = self.safety(value)
        self.Visa.write(":SOUR:WAVE:ABOR")
        self.Visa.write(":SOUR:WAVE:OFFS "+ str(self.safe_value))
        self.Visa.write(":SOUR:WAVE:ARM")
        self.Visa.write(":SOUR:WAVE:INIT")
        
    def set_curt(self, value):
        self.safe_value = self.safety(value)
        self.Visa.write(":OUTP OFF")
        self.Visa.write(":CURR "+ str(self.safe_value))
        self.Visa.write(":OUTP ON")

    def read_ampl(self):
        return float(self.Visa.query(":SOUR:WAVE:AMPL?").replace("\n", "").split(",")[0])
    
    def read_freq(self):
        return float(self.Visa.query(":SOUR:WAVE:FREQ?").replace("\n", "").split(",")[0])
    
    def read_offs(self):
        return float(self.Visa.query(":SOUR:WAVE:OFFS?").replace("\n", "").split(",")[0])
    
    def read_curt(self):
        return float(self.Visa.query(":CURR?").replace("\n", "").split(",")[0])
    
    
    def arm_off(self):
        self.Visa.write(":SOUR:WAVE:ABOR")
    
    def output_on(self):
        self.Visa.write(":SOUR:WAVE:ABOR")
        self.Visa.write(":SOUR:WAVE:ARM")
        self.Visa.write(":SOUR:WAVE:INIT")

    def output_off(self):
        self.Visa.write(":OUTP OFF")
        
    def compliance_error(self):
        comp_bool = False
        if int(self.Visa.query(":STAT:MEAS:COND?")) == 8:
            comp_bool = True
        return comp_bool
        
if __name__ == "__main__":
    
    kei6221_ref = Keithley6221('GPIB1::12::INSTR')
    kei6221_ref.ac_init(freq = 13, ampl = 3, offs = 0, func = "SIN")
    time.sleep(5)
    kei6221_ref.output_off()
