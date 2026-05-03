from setScanFunction import setScanFunction
from data import data
from sequence import sequence
from connectInstruments import connection
from Notification import notice
import logging

class measurementVM():
    def __init__(self, variableSet, data_callback=None):
        self.variableSet = variableSet
        self.data_callback = data_callback
        self.dataVM = data(self.variableSet)
        self.connectionVM = connection(self.variableSet, self.dataVM)
        
        self.setScanFunction = setScanFunction(self.variableSet, self.dataVM, data_callback=self.data_callback)
        self.sequenceVM = sequence(self.variableSet)
        self.notificationVM = notice(self.variableSet)

        pass

    def initializeSetup(self, instrumentsList):
        print("Sequence Read")
        self.sequenceVM.readSequence(self.variableSet.sequenceDirectory)
        
        #Current ON
        print("Current ON")
        self.setScanFunction.CurrentControl(instrumentsList, 1)
        self.setScanFunction.setScannerFullOpen(3, instrumentsList)
        pass

    def FinishMeasurementSetup(self, instrumentsList):        
        #Current OFF
        print("Current OFF")
        self.setScanFunction.CurrentControl(instrumentsList, 0)
        self.setScanFunction.setScannerFullOpen(3, instrumentsList)
        pass

    def startMeasurement(self):

        print("Load Instruments")
        self.connectionVM.connect_PPMS()
        self.connectionVM.connect_LI5600()
        self.connectionVM.connect_Keithley6221()
        # self.connectionVM.connect_LakeShore()
        self.connectionVM.connect_ADCMT3100()

        with self.connectionVM.connectInstrument() as instrumentsList:
            self.initializeSetup(instrumentsList)
            
            # Notify UI about the sequence content
            from flask_socketio import SocketIO
            # We need to be careful about importing socketio here if it's already in web_app
            # Instead, let's use a callback or a shared event system if possible
            # Or just rely on the logging for now and update web_app to handle it.
            # Actually, web_app.py has access to measureVM.
            
            self.dataVM.run_logger()
            total_steps = len(self.variableSet.commandList)
            for i, sequenceLine in enumerate(self.variableSet.commandList):
                if self.variableSet.StopMeasurementFlag > 0:
                    print(f"SafetyFlag: {self.variableSet.StopMeasurementFlag}")
                    self.variableSet.currentCommand = "Aborted"
                    break
                
                cmd_name = sequenceLine["command"]
                self.variableSet.currentCommand = f"{cmd_name} ({i+1}/{total_steps})"
                logging.info(f"Step {i+1}/{total_steps}: {cmd_name}")

                if cmd_name in ["setPOS", "setTemp", "setField", "setAmp", "setScannerOpenClose", "setScannerScanList"]:
                    self.setScanFunction.runsetFunction(sequenceLine, instrumentsList)
                elif sequenceLine["command"] in ["scanPOS", "scanTemp", "scanField", "scanAmp", "scanFreq", "scanOffset"]:
                    self.setScanFunction.runScanFunction(sequenceLine, instrumentsList)
                elif sequenceLine["command"] in ["CurrentControl"]:
                    self.setScanFunction.runCurrentControl(sequenceLine, instrumentsList)
                elif sequenceLine["command"] in ["NewFile"]:
                    self.setScanFunction.runNewFileFunction(sequenceLine)
                    # Make NEW file and start to save data to the file.
                elif sequenceLine["command"] in ["END"]:
                    print("Measurement_Done")
                    break        
                else:
                    print(f"There are no such command")
                
            self.FinishMeasurementSetup(instrumentsList)

        return


if __name__ =="__main__":

    class variablesModel():
        def __init__(self):
            # ------------ Logging ------------ #
            self.loggerDirectory = r"C:\Users\98she\OneDrive\デスクトップ\log.log"
            self.loggerLevel = logging.DEBUG
            # ------------ Logging ------------ #


            # ------------ Measurement Setup ------------ #
            self.sequenceDirectory = ""
            self.dataSaveDirectory = ""
            self.dataSaveFileName = ""
            self.commandList = []
            self.connectedInstrumentList = []
            self.connectedInstrumentReferenceList = []
            # ------------ Measurement Setup ------------ #


            # ------------ LIA ------------ #
            self.frequency = 13
            self.Harmonics = 1
            self.Averaging = 100
            self.parameters_mode = "AUTO"
            self.parameters_table = None
            # ------------ LIA ------------ #


            # ------------ Current Status ------------ #
            self.currentField = 0
            self.currentTemp = 0
            self.currentPOS = 0
            self.currentAmp = 0
            self.currentHeLevel = 0
            self.currentFreq = 0
            self.currentOffset = 0
            self.currentTime = 0
            # ------------ Current Status ------------ #
            pass
    
    testVariableSet = variablesModel()
    test = measurementVM(testVariableSet)
    test.startMeasurement()