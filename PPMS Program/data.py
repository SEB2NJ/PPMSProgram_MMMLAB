import os
import logging
import pandas as pd

class data():
    def __init__(self, variableSet):
        self.variableSet = variableSet
        self.current_filepath = None 
        self.logger = self.setup_logger(self.variableSet.loggerDirectory, "Logger", self.variableSet.loggerLevel)
        self.PPMSLogger = self.setup_logger(self.variableSet.loggerDirectory, "PPMSLogger", self.variableSet.loggerLevel)
        self.LI5600Logger = self.setup_logger(self.variableSet.loggerDirectory, "LI5600Logger", self.variableSet.loggerLevel)
        self.LakeShoreLogger = self.setup_logger(self.variableSet.loggerDirectory, "LakeShoreLogger", self.variableSet.loggerLevel)
        self.Keithley6221Logger = self.setup_logger(self.variableSet.loggerDirectory, "Keithley6221Logger", self.variableSet.loggerLevel)

    def createDatFile(self, filename="measurement_data.dat"):
        save_dir = getattr(self.variableSet, 'dataSaveDirectory', None)
        if not save_dir:
            print("[Warning] Save to the Default Directory")
            save_dir = "./Data"

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        if not filename.endswith(".dat"):
            filename += ".dat"

        full_path = os.path.join(save_dir, filename)

        with open(full_path, 'w', encoding='utf-8') as f:
            pass
            
        self.current_filepath = full_path
        return full_path

    def appendDataLine(self, data_values):
        if self.current_filepath is None:
            print("[Error] No such file.")
            return

        with open(self.current_filepath, 'a', encoding='utf-8') as f:
            if isinstance(data_values, (list, tuple)):
                line_to_write = ",".join(map(str, data_values))
            else:
                line_to_write = str(data_values)
            
            f.write(line_to_write + "\n")
    
    def setup_logger(self, log_file=None, logger_name="Logger", level=logging.DEBUG):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

        # すでにハンドラが設定されている場合は何もしない（重複防止）
        if logger.hasHandlers():
            return logger

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

        # コンソール出力
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # ファイル出力（指定された場合）
        if log_file:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger
    
    def run_logger(self):
        self.logger = self.logger or logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False
        self.logger.debug("FileOperation インスタンスが作成されました。")
        pass


    def setLIASettingList(self, SettingList):
            keys = [
                "Harm1_DynamicReserve", "Harm1_FilterSlope", "Harm1_TimeConstant", 
                "Harm1_VoltageRange", "Harm1_Phase"
            ]
            
            result_list = []
            for values in SettingList:
                setting_dict = dict(zip(keys, values))
                result_list.append(setting_dict)
                
            return result_list
        


    def SaveFile(self, FileName, data, mode="a", PPMS_dat=True):
        df = pd.DataFrame(data)

        FileAddress = os.path.join(self.variableSet.dataSaveDirectory, FileName + ".dat")
        os.makedirs(self.variableSet.dataSaveDirectory, exist_ok=True)

        is_new_file = not os.path.exists(FileAddress) or mode == "w"

        try:
            if is_new_file:
                if PPMS_dat:
                    with open(FileAddress, "w", encoding="utf-8") as f:
                        f.write("[Header]\nINFO, a\n[Data]\n")
                    df.to_csv(FileAddress, index=False, mode="a", header=True)
                else:
                    df.to_csv(FileAddress, index=False, mode="w", header=True)
            else:
                df.to_csv(FileAddress, index=False, mode="a", header=False)

            logging.getLogger("FileOperation").info(f"ファイル保存: {FileAddress}")

        except Exception as e:
            logging.getLogger("FileOperation").exception(f"保存エラー: {e}")


if __name__ == "__main__":
    # --- test --- #
    class DummyVariableSet:
        def __init__(self):
            self.dataSaveDirectory = r"C:\Users\98she\OneDrive\デスクトップ\MyMeasurementData"

    my_vars = DummyVariableSet()
    my_data_manager = data(my_vars)
