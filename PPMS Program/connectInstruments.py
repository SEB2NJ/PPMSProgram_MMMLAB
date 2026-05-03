from contextlib import ExitStack, contextmanager

from InstrumentsClass.PPMS import PPMS
from InstrumentsClass.LI5660 import LI5600
from InstrumentsClass.LakeShore import LakeShore155
from InstrumentsClass.keithley6221 import Keithley6221
from InstrumentsClass.ADCMT3100 import ADCMT3100

class connection():
    def __init__(self, variableSet, dataVM):
        self.variableSet = variableSet
        self.dataVM = dataVM
        self.isDebugMode = True
        pass

    def connect_PPMS(self):
        self.variableSet.connectedInstrumentList.append("PPMS")
        pass
    
    def connect_LI5600(self):
        self.variableSet.connectedInstrumentList.append("LI5600")
        pass

    def connect_LakeShore(self):
        self.variableSet.connectedInstrumentList.append("LakeShore")
        pass

    def connect_Keithley6221(self):
        self.variableSet.connectedInstrumentList.append("Keithley6221")
        pass

    def connect_ADCMT3100(self):
        self.variableSet.connectedInstrumentList.append("ADCMT3100")
        pass



    @contextmanager
    def connectInstrument(self):
        with ExitStack() as stack:
            active_resources = {}
            
            if "PPMS" in self.variableSet.connectedInstrumentList:
                active_resources["PPMS_ref"] = stack.enter_context(PPMS(logger = self.dataVM.PPMSLogger))
                
            if "LakeShore" in self.variableSet.connectedInstrumentList:
                active_resources["LakeShore_ref"] = stack.enter_context(LakeShore155(resource_name = "TCPIP0::100.100.1.155::7777::SOCKET", logger = self.dataVM.LakeShoreLogger)) # to LakeShore
            
            if "ADCMT3100" in self.variableSet.connectedInstrumentList:
                active_resources["ADCMT3100_ref"] = stack.enter_context(ADCMT3100(resource_name = "GPIB1::20::INSTR")) # to LakeShore
            
            if "Keithley6221" in self.variableSet.connectedInstrumentList:
                active_resources["Keithley6221_ref"] = stack.enter_context(Keithley6221(resource_name = 'GPIB1::12::INSTR', variableSet=self.variableSet)) # to keithley
            
            if "LI5600" in self.variableSet.connectedInstrumentList:
                if len(self.variableSet.Harmonics) == 1:
                    active_resources["LI5600_ref"] = stack.enter_context(LI5600(resource_name = "TCPIP0::100.100.1.55::5025::SOCKET", logger = self.dataVM.LI5600Logger)) # to LakeShore
                elif len(self.variableSet.Harmonics) > 1:
                    active_resources["LI5600_ref"] = stack.enter_context(LI5600(resource_name = "TCPIP0::100.100.1.55::5025::SOCKET", logger = self.dataVM.LI5600Logger)) # to LakeShore
                    active_resources["LI5600_ref2"] = stack.enter_context(LI5600(resource_name = "TCPIP0::100.100.1.56::5025::SOCKET", logger = self.dataVM.LI5600Logger)) # to LakeShore
            yield active_resources



if __name__ =="__main__":

    pass
        
