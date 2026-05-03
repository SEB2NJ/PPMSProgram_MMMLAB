import time
import pandas as pd

class setScanFunction():
    def __init__(self, variableSet, dataVM, data_callback=None):
        self.variableSet = variableSet
        self.dataVM = dataVM
        self.data_callback = data_callback
        pass

    def runsetFunction(self, sequenceLine, instrumentsList):
        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]
            
        if "LI5600_ref" in instrumentsList:
            LI5600_ref = instrumentsList["LI5600_ref"]

        if "ADCMT3100_ref" in instrumentsList:
            ADCMT3100_ref = instrumentsList["ADCMT3100_ref"]

        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]

        if "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]        
        
        command = sequenceLine.get("command")

        match command:
            case "setPOS":
                target = float(sequenceLine.get("target"))
                self.setPos(target, instrumentsList)
                
            case "setTemp":
                target = float(sequenceLine.get("target"))
                rate = float(sequenceLine.get("rate"))
                waittime = float(sequenceLine.get("waittime"))
                self.setTemp(target, rate, waittime, instrumentsList)
                
            case "setField":
                target = float(sequenceLine.get("target"))
                approach = int(sequenceLine.get("approach"))
                mode = int(sequenceLine.get("mode"))
                waittime = float(sequenceLine.get("waittime"))
                self.setField(target, approach, mode, waittime, instrumentsList)
                
            case "setAmp":
                target = float(sequenceLine.get("target"))
                frequency = float(sequenceLine.get("frequency"))
                offset = float(sequenceLine.get("offset"))
                waittime = float(sequenceLine.get("waittime"))
                self.setAmp(target, frequency, offset, waittime, instrumentsList)
            
            case "setScannerOpenClose":
                CHList = list(sequenceLine.get("CHList"))
                toOpen = int(sequenceLine.get("toOpen"))
                waittime = float(sequenceLine.get("waittime"))
                self.setScannerOpenClose(CHList, toOpen, waittime, instrumentsList)
            
            case "setScannerScanList":
                CHList = list(sequenceLine.get("CHList"))
                LIASettingList = list(sequenceLine.get("LIASettingList"))
                HarmonicsList = list(sequenceLine.get("HarmonicsList"))

                print(f"setScannerScanList: {CHList}")
                self.variableSet.signalCH = CHList
                self.variableSet.Harmonics = HarmonicsList
                self.variableSet.LIASetting_1 = self.dataVM.setLIASettingList(LIASettingList)
                
            case _:
                print(f"No Such Command: {command}")
        pass

    def runScanFunction(self, sequenceLine, instrumentsList):
        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]
            
        if "LI5600_ref" in instrumentsList:
            LI5600_ref = instrumentsList["LI5600_ref"]

        if "ADCMT3100_ref" in instrumentsList:
            ADCMT3100_ref = instrumentsList["ADCMT3100_ref"]

        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]

        if "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]   

        command = sequenceLine.get("command")
        


        match command:
            case "scanPOS":
                initial = float(sequenceLine.get("initial"))
                final = float(sequenceLine.get("final"))
                increment = float(sequenceLine.get("increment"))
                waittime = float(sequenceLine.get("waittime"))
                self.scanPOS(initial, final, increment, waittime, instrumentsList)

            case "scanField":
                initial = float(sequenceLine.get("initial"))
                final = float(sequenceLine.get("final"))
                increment = float(sequenceLine.get("increment"))
                approach = int(sequenceLine.get("approach"))
                mode = int(sequenceLine.get("mode"))
                waittime = float(sequenceLine.get("waittime"))
                
                self.scanField(initial, final, increment, approach, mode, waittime, instrumentsList)
                
            case "scanAmp":
                initial = float(sequenceLine.get("initial"))
                final = float(sequenceLine.get("final"))
                increment = float(sequenceLine.get("increment"))
                frequency = float(sequenceLine.get("frequency"))
                offset = float(sequenceLine.get("offset"))
                waittime = float(sequenceLine.get("waittime"))
                
                self.scanAmp(initial, final, increment, frequency, offset, waittime, instrumentsList)

            case "scanFreq":
                FreqList = list(sequenceLine.get("FreqList"))
                current = float(sequenceLine.get("current"))
                offset = float(sequenceLine.get("offset"))
                waittime = float(sequenceLine.get("waittime"))
                
                self.scanFreq(FreqList, current, offset, waittime, instrumentsList)

            case "scanOffset":
                initial = float(sequenceLine.get("initial"))
                final = float(sequenceLine.get("final"))
                increment = float(sequenceLine.get("increment"))
                current = float(sequenceLine.get("current"))
                frequency = float(sequenceLine.get("frequency"))
                waittime = float(sequenceLine.get("waittime"))
                
                self.scanOffset(initial, final, increment, current, frequency, waittime, instrumentsList)
                
            case "scanTemp":
                initial = float(sequenceLine.get("initial"))
                final = float(sequenceLine.get("final"))
                increment = float(sequenceLine.get("increment"))
                rate = float(sequenceLine.get("rate"))
                waittime = float(sequenceLine.get("waittime"))
                self.scanTemp(initial, final, increment, rate, waittime, instrumentsList)
                
            case _:
                print(f"No Such Command: {command}")
    
    def runNewFileFunction(self, sequenceLine):
            NewName = sequenceLine.get("fileName")
            self.variableSet.dataSaveFileName = NewName

    def runCurrentControl(self, sequenceLine, instrumentsList):
        command = sequenceLine.get("command")
        match command:
            case "CurrentControl":
                CurrentOnOff = int(sequenceLine.get("CurrentOnOff"))

        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]
            match CurrentOnOff:
                case 0:
                    #current OFF
                    LakeShore_ref.output_ON()
                    pass
                case 1:
                    # current ON
                    LakeShore_ref.output_OFF()
                    pass

        elif "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"] 
            match CurrentOnOff:
                case 0:
                    #current OFF
                    print("KeithleyCurrentOn...TobeAdded")
                    pass
                case 1:
                    # current ON
                    print("KeithleyCurrentOFF...TobeAdded")
                    pass
            
        pass

    def CurrentControl(self, instrumentsList, OnOff):
        if "LakeShore_ref" in instrumentsList:
            if OnOff == 1:
                LakeShore_ref = instrumentsList["LakeShore_ref"]
                LakeShore_ref.AC_initialize(self.variableSet.currentAmp, self.variableSet.currentFreq, terminal = "REAR")
                LakeShore_ref.output_ON()
            else:
                LakeShore_ref = instrumentsList["LakeShore_ref"]
                LakeShore_ref.output_OFF()
                
        elif "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]  
            if OnOff == 1:
                Keithley6221_ref = instrumentsList["Keithley6221_ref"]
                Keithley6221_ref.output_on()
            else:
                Keithley6221_ref = instrumentsList["Keithley6221_ref"]
                Keithley6221_ref.output_off()
        pass

    def saveData(self, instrumentsList):

        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]

        if "ADCMT3100_ref" in instrumentsList:
            ADCMT3100_ref = instrumentsList["ADCMT3100_ref"]
            
        if "LI5600_ref" in instrumentsList:
            LI5600_ref = instrumentsList["LI5600_ref"]
        
        if "LI5600_ref2" in instrumentsList:
            LI5600_ref2 = instrumentsList["LI5600_ref2"]
        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]

        if "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]    

        self.getCurrentStatus(instrumentsList)

        print(self.variableSet.signalCH)
        if len(self.variableSet.signalCH) == 0:

            StatusData = pd.DataFrame([[self.variableSet.currentTime, 
                                        self.variableSet.currentField, 
                                        self.variableSet.currentTemp, 
                                        self.variableSet.currentPOS, 
                                        self.variableSet.currentAmp, 
                                        self.variableSet.currentFreq, 
                                        self.variableSet.currentOffset,
                                        self.variableSet.currentHeLevel]], 
                                    columns=["Time", "Field", "Temp", "POS", "Amp", "Freq", "Offset", "HeLevel"])
            if len(self.variableSet.Harmonics) == 1:
                # self.setLIAParameter(LI5600_ref, 1)
                print("Start To Get Data")
                Result, parameters = LI5600_ref.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[0]], 
                                            Averaging=[self.variableSet.Averaging[0]],
                                            mode = "MANUAL",
                                            Manual_parameter = self.variableSet.LIASetting_1[0]
                                            )
                Results = pd.concat([StatusData, Result, parameters], axis=1)
                print("Get Data Done")

            if len(self.variableSet.Harmonics) > 1:

                print("Start To Get Data")
                Result, parameters = LI5600_ref.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[0]], 
                                            Averaging=[self.variableSet.Averaging[0]],
                                            mode = "MANUAL",
                                            Manual_parameter = self.variableSet.LIASetting_1[0]
                                            )
                Result2, parameters2 = LI5600_ref2.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[1]], 
                                            Averaging=[self.variableSet.Averaging[1]],
                                            mode = "MANUAL",
                                            Manual_parameter = self.variableSet.LIASetting_2[0]
                                            )
                Results = pd.concat([StatusData, Result, Result2, parameters, parameters2], axis=1)
                print("Get Data Done")

            self.dataVM.SaveFile(self.variableSet.dataSaveFileName, Results)
            if self.data_callback:
                self.data_callback(Results.to_dict('records')[0])
        else:
            for index, CHNum in enumerate(self.variableSet.signalCH):
                self.setScannerOpenClose(CHNum, 0, 3, instrumentsList)

                StatusData = pd.DataFrame([[self.variableSet.currentTime, 
                                            self.variableSet.currentField, 
                                            self.variableSet.currentTemp, 
                                            self.variableSet.currentPOS, 
                                            self.variableSet.currentAmp, 
                                            self.variableSet.currentFreq, 
                                            self.variableSet.currentOffset,
                                            self.variableSet.currentHeLevel]], 
                                        columns=["Time", "Field", "Temp", "POS", "Amp", "Freq", "Offset", "HeLevel"])
                if len(self.variableSet.Harmonics) == 1:
                    # self.setLIAParameter(LI5600_ref, 1)
                    print("Start To Get Data2")
                    Result, parameters = LI5600_ref.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[0]], 
                                                Averaging=[self.variableSet.Averaging[0]],
                                                mode = "MANUAL",
                                                Manual_parameter = self.variableSet.LIASetting_1[index]
                                                )
                    Results = pd.concat([StatusData, Result, parameters], axis=1)
                    print("Get Data Done")

                if len(self.variableSet.Harmonics) > 1:

                    print("Start To Get Data")
                    Result, parameters = LI5600_ref.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[0]], 
                                                Averaging=[self.variableSet.Averaging[0]],
                                                mode = "MANUAL",
                                                Manual_parameter = self.variableSet.LIASetting_1[index]
                                                )
                    Result2, parameters2 = LI5600_ref2.harmonic_measurement_loop(Harmonics=[self.variableSet.Harmonics[1]], 
                                                Averaging=[self.variableSet.Averaging[1]],
                                                mode = "MANUAL",
                                                Manual_parameter = self.variableSet.LIASetting_2[index]
                                                )
                    Results = pd.concat([StatusData, Result, Result2, parameters, parameters2], axis=1)
                    print("Get Data Done")

                    
                saveFileName = self.variableSet.dataSaveFileName + str(CHNum)
                self.dataVM.SaveFile(saveFileName, Results)
                if self.data_callback:
                    self.data_callback(Results.to_dict('records')[0])
                self.setScannerOpenClose(CHNum, 1, 3, instrumentsList)
        pass

    def setLIAParameter(self, LIAInstance, MachineNum):
        print("SET LIA Param.")
        
        LIAInstance.set_dynamic_reserve(self.variableSet.dynamicRange[MachineNum - 1])
        LIAInstance.set_voltage_range(self.variableSet.range[MachineNum - 1])

        if self.variableSet.timeConstant[MachineNum - 1] not in [  1e-6, 2e-6, 5e-6,
                    1e-5, 2e-5, 5e-5,
                    1e-4, 2e-4, 5e-4,
                    1e-3, 2e-3, 5e-3,
                    1e-2, 2e-2, 5e-2,
                    1e-1, 2e-1, 5e-1,
                    1.0, 2.0, 5.0,
                    1e1, 2e1, 5e1,
                    1e2, 2e2, 5e2,
                    1e3, 2e3, 5e3,
                    1e4, 2e4, 5e4]:
            print("TimeConstant Set error")
            self.variableSet.timeConstant[MachineNum - 1] = 1.0
        LIAInstance.set_filter_time_constant(self.variableSet.timeConstant[MachineNum - 1])

        if self.variableSet.slope[MachineNum - 1] not in [6, 12, 18, 24]:
            print("Slope Set Error")
            self.variableSet.slope[MachineNum - 1] = 24
        LIAInstance.set_filter_slope(self.variableSet.slope[MachineNum - 1])
        pass

    def getCurrentStatus(self, instrumentsList):

        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]
            
        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]
            self.variableSet.currentAmp = LakeShore_ref.get_current_mA()
            self.variableSet.currentFreq = LakeShore_ref.get_frequency()
            self.variableSet.currentOffset = LakeShore_ref.get_current_offset()

        if "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]
            self.variableSet.currentAmp = Keithley6221_ref.read_ampl()
            self.variableSet.currentFreq = Keithley6221_ref.read_freq()
            self.variableSet.currentOffset = Keithley6221_ref.read_offs()
        
        self.variableSet.currentField, self.variableSet.fieldStatus = ppms_ref.get_field()
        self.variableSet.currentTemp, self.variableSet.tempStatus = ppms_ref.get_temperature()
        self.variableSet.currentPOS, self.variableSet.posStatus = ppms_ref.get_position()
        self.variableSet.currentHeLevel = ppms_ref.get_level()
        self.variableSet.currentTime = time.time()

        pass

    
# ----------------- setFunctions ----------------- #

    def setField(self, target, approach, mode, waittime, instrumentsList):

        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]

        if abs(target) > 90000:
            print("Field Limit is +-90000 Oe")
            return
        
        currentField, status = ppms_ref.get_field()
        self.variableSet.fieldStatus = status
        if abs(target - float(currentField)) < 5:
            print(f"Field Already at {target}.")
            return
        
        HeLevel = ppms_ref.get_level()
        if float(HeLevel) < self.variableSet.sweepHField_HeLevelLimit:
            print(f"He Level Low: {HeLevel}")
            self.variableSet.StopMeasurementFlag = 1
            return
        
        if self.variableSet.StopMeasurementFlag != 0:
            print(f"SafetyFlag: {self.variableSet.StopMeasurementFlag}")
            ppms_ref.set_field(0, 100, approach, mode, waittime, 10)
            print(f"Set Field 0 --- HeLevel: {HeLevel}")
            return
        
        self.variableSet.currentField = target
        match approach:
            case 0:
                approach = "linear"
            case 1:
                approach = "no_overshoot"
            case 2:
                approach = "oscillate"
            case _:
                print("No such APPROACH mode.")
                return
        
        match mode:
            case 0:
                mode = "persistent"
            case 1:
                mode = "driven"
            case _:
                print("No such FieldMode.")
                return
        print(f"Set Field. target:{target}, approach:{approach}, mode:{mode}, waittime:{waittime}, HeLevel: {HeLevel}")
        ppms_ref.set_field(target, 100, approach, mode, waittime, 10)
        currentField, status = ppms_ref.get_field()
        self.variableSet.currentField = currentField
        self.variableSet.fieldStatus = status
        print(f"Field Set: {currentField}")

        pass

    def setTemp(self, target, rate, waittime, instrumentsList):
        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]

        if target < 4.2 or target >= 400:
            print("Temp Limit is 2 - 400 degC")
            return
        self.variableSet.currentTemp = target
        print(f"Set Temp. target:{target}, rate:{rate}, waittime:{waittime}")
        ppms_ref.set_temperature(target, rate, None, waittime, 10)
        currentTemp, status = ppms_ref.get_temperature()
        self.variableSet.currentTemp = currentTemp
        self.variableSet.tempStatus = status
        print(f"Temp Set: {currentTemp}")

        pass

    def setPos(self, target, instrumentsList):
        if "PPMS_ref" in instrumentsList:
            ppms_ref = instrumentsList["PPMS_ref"]

        if target < -10.1 or target > 362:
            print("Angle Limit is -10 - 360 deg")
            return
        
        self.variableSet.currentPOS = target
        print(f"Set POS. target:{target}")
        ppms_ref.set_position(target, wait=True)
        currentPos, status = ppms_ref.get_position()
        self.variableSet.currentPOS = currentPos
        self.variableSet.posStatus = status
        print(f"POS Set: {currentPos}")

        pass
        ppms_ref.set_position(target, 1, True, "Transport stopped at set point")
        currentPOS, _ = ppms_ref.get_position()
        print(f"POS Set: {currentPOS}")
        pass

    def setAmp(self, target, frequency, offset, waittime, instrumentsList):

        if target > 25:
            print("Current Limit is < 25 mA")
            return

        self.variableSet.currentAmp = target
        self.variableSet.currentFreq = frequency
        self.variableSet.currentOffset = offset
        
        if "LakeShore_ref" in instrumentsList:
            LakeShore_ref = instrumentsList["LakeShore_ref"]
            LakeShore_ref.AC_initialize(target, frequency, "REAR")
            LakeShore_ref.output_ON()

        elif "Keithley6221_ref" in instrumentsList:
            Keithley6221_ref = instrumentsList["Keithley6221_ref"]
            Keithley6221_ref.ac_init(freq = frequency, ampl = target, offs = offset, func = "SIN")
        
        print(f"Amp set. target:{target}, frequency:{frequency}, offset:{offset}")
        time.sleep(waittime)
        pass

    def setScannerOpenClose(self, CHList, toOpen, waittime, instrumentsList):
        if "ADCMT3100_ref" in instrumentsList:
            ADCMT3100_ref = instrumentsList["ADCMT3100_ref"]

        if toOpen == 1:
            ADCMT3100_ref.ch_open(CHList)
            print(f"{CHList} Opened")
        elif toOpen == 0:
            ADCMT3100_ref.ch_close(CHList)
            print(f"{CHList} Closed")
        
        time.sleep(waittime)
    
    def setScannerFullOpen(self, waittime, instrumentsList):
        if "ADCMT3100_ref" in instrumentsList:
            ADCMT3100_ref = instrumentsList["ADCMT3100_ref"]

        ADCMT3100_ref.ch_fullopen()
        print("Scanner FullOpened")
        time.sleep(waittime)

# ----------------- setFunctions ----------------- #

# ----------------- scanFunctions ----------------- #

    def generateScanPoints(self, initial, final, increment):
        if increment == 0:
            return [initial]
        
        scanList = []
        current = initial
        step = abs(increment) if initial < final else -abs(increment)
        if initial < final:
            while current < final:
                scanList.append(round(current, 8))
                current += step
        else:
            while current > final:
                scanList.append(round(current, 8))
                current += step
        if not scanList or scanList[-1] != final:
            scanList.append(final)

        return scanList

    def scanPOS(self, initial, final, increment, waittime, instrumentsList):

        scanPoints = self.generateScanPoints(initial, final, increment)
        for target in scanPoints:
            self.setPos(target, instrumentsList)
            self.saveData(instrumentsList)

    def scanField(self, initial, final, increment, approach, mode, waittime, instrumentsList):

        scanPoints = self.generateScanPoints(initial, final, increment)
        for target in scanPoints:
            if self.variableSet.StopMeasurementFlag > 0:
                break
            self.setField(target, approach, mode, waittime, instrumentsList)
            self.saveData(instrumentsList)

    def scanAmp(self, initial, final, increment, frequency, offset, waittime, instrumentsList):

        scanPoints = self.generateScanPoints(initial, final, increment)
        for target in scanPoints:
            self.setAmp(target, frequency, offset, waittime, instrumentsList)
            self.saveData(instrumentsList)

    def scanFreq(self, FreqList, current, offset, waittime, instrumentsList):
        CHList = self.dataVM.signalCH
        for target in FreqList:
            self.setAmp(current, target, offset, waittime, instrumentsList)
            self.saveData(instrumentsList)

    def scanOffset(self, initial, final, increment, current, frequency, waittime, instrumentsList):

        scanPoints = self.generateScanPoints(initial, final, increment)
        for target in scanPoints:
            self.setAmp(current, frequency, target, waittime, instrumentsList)
            self.saveData(instrumentsList)

    def scanTemp(self, initial, final, increment, rate, waittime, instrumentsList):

        scanPoints = self.generateScanPoints(initial, final, increment)
        for target in scanPoints:
            self.setTemp(target, rate, waittime, instrumentsList)
            self.saveData(instrumentsList)

# ----------------- scanFunctions ----------------- #