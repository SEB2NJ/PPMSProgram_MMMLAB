from measurement import measurementVM
import logging
import os
import MainView

class main():
    def __init__(self):
        self.variableSet = variablesModel()
        self.measurementVM = measurementVM(self.variableSet)
        pass

class variablesModel():
    def __init__(self):
        self.LoggingVariable()
        self.measurementSetup()
        self.scannerSetup()
        self.LIASetup()
        self.currentStatusSetup()
        pass

    def LoggingVariable(self):
        # ------------ Logging ------------ #
        self.loggerDirectory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.log")
        self.loggerLevel = logging.INFO
        # ------------ Logging ------------ #
        pass

    def measurementSetup(self):
        # ------------ Measurement Setup ------------ #
        self.sequenceDirectory = r"C:\Users\PPMS\Desktop\UserData\SEBIN\TSCF\TSCF001\(11, 24)_AHE_1mA_300K_0_90deg_SEQ.dat"
        self.dataSaveDirectory = r"C:\Users\PPMS\Desktop\UserData\SEBIN\TSCF\TSCF001"
        self.dataSaveFileName = ""
        self.commandList = []
        self.connectedInstrumentList = []
        self.kei6221ComplienceVoltage = 25
        # ------------ Measurement Setup ------------ #
        pass


    def scannerSetup(self):
        self.signalCH = []
        pass

    def LIASetup(self):
        # ------------ LIA ------------ #
        self.frequency = 13
        self.Harmonics = [1]
        self.Averaging = [100]
        self.LIASetting_1 = [{"Harm1_DynamicReserve": "LOW",
                                "Harm1_FilterSlope": 24,
                                "Harm1_TimeConstant": 0.2,
                                 "Harm1_VoltageRange": 0.1,
                                 "Harm1_Phase": 0
                                 }]
        
        self.LIASetting_2 = [{"Harm2_DynamicReserve": "LOW",
                                "Harm2_FilterSlope": 24,
                                "Harm2_TimeConstant": 1,
                                 "Harm2_VoltageRange": 0.1,
                                 "Harm2_Phase": 0}]
        self.parameters_mode = "AUTO"
        self.parameters_table = None
        # ------------ LIA ------------ #
        pass

    def currentStatusSetup(self):
        # ------------ Current Status ------------ #
        self.currentField = 0
        self.fieldStatus = "Idle"
        self.currentTemp = 0
        self.tempStatus = "Idle"
        self.currentPOS = 0
        self.posStatus = "Idle"
        self.currentAmp = 0.02
        self.currentHeLevel = 0
        self.currentFreq = 13
        self.currentOffset = 0
        self.currentTime = 0
        self.currentCommand = "Idle"
        
        self.StopMeasurementFlag = 0
        self.sweepHField_HeLevelLimit = 60.3
        # ------------ Current Status ------------ #
        pass




if __name__ =="__main__":
    MainView.main()

