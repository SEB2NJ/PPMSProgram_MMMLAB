import os
import ast

class sequence():
    COMMAND_SCHEMA = {
        'setPOS': ['target'],
        'setTemp': ['target', 'rate', 'waittime'],
        'setField': ['target', 'approach', 'mode', 'waittime'],
        'setAmp': ['target', 'frequency', 'offset', 'waittime'],
        'setScannerOpenClose': ['CHList', 'toOpen', 'waittime'],
        'setScannerScanList': ['CHList', 'HarmonicsList', 'LIASettingList'],
        'scanPOS':['initial', 'final', 'increment', 'waittime'],
        'scanTemp':['initial', 'final', 'increment', 'rate', 'waittime'],
        'scanField':['initial', 'final', 'increment', 'approach', 'mode', 'waittime'],
        'scanAmp':['initial', 'final', 'increment', 'frequency', 'offset', 'waittime'],
        'scanFreq':['FreqList', 'current', 'offset', 'waittime'],
        'scanOffset':['initial', 'final', 'increment', 'current', 'frequency', 'waittime'],
        'CurrentControl': ['CurrentOnOff'],
        'NewFile': ['fileName'],
        'END': []
    }

    def __init__(self, variableSet):
        self.variableSet = variableSet
        self.isSequenceStarted = False

    def set_sequenceDirectory(self, fileAddress):
        self.variableSet.sequenceDirectory = fileAddress

    def readSequence(self, file_path):
        self.variableSet.commandList = []
        self.isSequenceStarted = False
        
        if not os.path.exists(file_path):
            print(f"[Error] No such Sequence File: {file_path}")
            return
            
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                row = []
                current_val = []
                depth = 0
                for char in line:
                    if char == '[':
                        depth += 1
                        current_val.append(char)
                    elif char == ']':
                        depth -= 1
                        current_val.append(char)
                    elif char == ',' and depth == 0:
                        row.append(''.join(current_val).strip())
                        current_val = []
                    else:
                        current_val.append(char)
                
                if current_val:
                    row.append(''.join(current_val).strip())
                # -----------------------------------------------------------
                
                command = row[0]
                
                if not self.isSequenceStarted:
                    if command == 'START':
                        self.isSequenceStarted = True
                    continue 
                                
                if command not in self.COMMAND_SCHEMA:
                    print(f"[Warning] No such command: {command}")
                    continue
                
                parsed_command = {'command': command}
                
                raw_values = [val for val in row[1:] if val != '']
                expected_keys = self.COMMAND_SCHEMA[command]
                
                for key, val in zip(expected_keys, raw_values):
                    if val.startswith('[') and val.endswith(']'):
                        try:
                            val = ast.literal_eval(val)
                        except Exception as e:
                            print(f"[Error] Failed to Convert to list ({val}): {e}")
                            
                    parsed_command[key] = val
                    
                for key in expected_keys:
                    if key not in parsed_command:
                        parsed_command[key] = ''
                        
                self.variableSet.commandList.append(parsed_command)
                
                if command == 'END':
                    break

    def get_sequence_list(self):
        result = []
        for cmd in self.variableSet.commandList:
            line_dict = {k: v for k, v in cmd.items() if v != ''}
            result.append(line_dict)
        return result

    def print_commands(self):
        for i, cmd in enumerate(self.variableSet.commandList, start=1):
            command_name = cmd['command']
            args_str = ", ".join([f"{k}: {v}" for k, v in cmd.items() if k != 'command' and v != ''])
            
            if command_name == 'END':
                print(f"Step {i:02d} | Command: {command_name:<8} | [END]")
            else:
                print(f"Step {i:02d} | Command: {command_name:<8} | {args_str}")


if __name__ == "__main__":
    class DummyVariableSet:
        def __init__(self):
            self.commandList = []

    my_vars = DummyVariableSet()
    my_seq = sequence(my_vars)
    
    test_dat_content = """START
setPOS, 90
setScannerOpenClose, [1, 3], 0, 10
setScannerScanList, [[2, 4], [6, 8]]
END"""
    with open("ConnectionTest.dat", "w") as f:
        f.write(test_dat_content)
        
    dat_file_path = "ConnectionTest.dat"

    my_seq.readSequence(dat_file_path)
    
    print(my_seq.get_sequence_list())

if __name__ == "__main__":
    class DummyVariableSet:
        def __init__(self):
            self.commandList = []

    my_vars = DummyVariableSet()
    my_seq = sequence(my_vars)
    
    dat_file_path = r"C:\Users\PPMS\Desktop\UserData\SEBIN\TSCF\TSCF001\AHE_1mA_300K_90deg_SEQ.dat"

    my_seq.readSequence(dat_file_path)
    
    print(my_seq.get_sequence_list())