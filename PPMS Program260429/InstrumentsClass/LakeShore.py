#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import logging
import pyvisa
import time
import atexit
import sympy
from IPython.display import clear_output
from datetime import datetime

class LakeShore155:
    def __init__(self, resource_name: str, logger: logging.Logger = None, timeout: int = 5000):
        self.rm = pyvisa.ResourceManager()
        self.instrument = self.rm.open_resource(resource_name)
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False
        self.logger.debug(f"Connected to {resource_name}")
        self._closed = False
        self.instrument.timeout = timeout
        self.instrument.read_termination = '\n'
        self.instrument.write_termination = '\n'
        atexit.register(self._cleanup)

    def __enter__(self):
        return self

    # def __exit__(self, exc_type, exc_value, traceback):
    #     self.close()

    def __exit__(self, exc_type, exc_val, traceback):
        try:
            if self.output_state:
                self.logger.info("Ensuring LakeShore155 output is turned OFF")
                self.output_OFF()
        except Exception as e:
            self.logger.error(f"Failed to turn off output on exit: {e}")
        finally:
            try:
                self.close()
            except Exception:
                pass

    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        if not self._closed:
            try:
                self.close()
            except Exception:
                pass  # ログなしで安全にスルー

    def close(self):
        if not self._closed:
            try:
                if self.output_check():
                    self.logger.info("Output was ON. Turning OFF before closing.")
                    self.output_OFF()
            except Exception as e:
                self.logger.warning(f"Could not turn output OFF during close: {e}")

            self.logger.info("Closing LakeShore155 connection.")
            self.instrument.close()
            self.rm.close()
            self._closed = True

    def clear_log(self, update=True):
        if update:
            try:
                clear_output(wait=True)
                self.logger.debug("セル出力をクリアしました")
            except Exception as e:
                self.logger.warning(f"clear_output に失敗: {e}")

    

    def write(self, command: str, log_level: int = None):
        if log_level is None:
            log_level = self._get_log_level_for_command(command, is_query=False)
        self.logger.log(log_level, f">> {command}")
        self.instrument.write(command)

    def query(self, command: str, log_level: int = None) -> str:
        if log_level is None:
            log_level = self._get_log_level_for_command(command, is_query=True)
        self.logger.log(log_level, f"?? {command}")
        response = self.instrument.query(command)
        self.logger.log(log_level, f"<< {response.strip()}")
        return response
    
    def _get_log_level_for_command(self, command: str, is_query: bool) -> int:
        cmd = command.strip().upper()

        if "*RST" in cmd or "OUTP:STAT 1" in cmd:
            return logging.INFO
        elif "SYST:ERR" in cmd:
            return logging.WARNING
        elif "OUTP:STAT 0" in cmd or "CLEAR" in cmd or "*CLS" in cmd:
            return logging.INFO
        elif any(k in cmd for k in ["SET", "SOUR:", "VOLT", "CURR", "ROUT", "TRIG", "PHAS"]):
            return logging.DEBUG
        elif is_query:
            return logging.DEBUG
        else:
            return logging.DEBUG


    def reset(self):
        self.write('*RST')

    def clear(self):
        self.write('*CLS')

    def identify(self):
        return self.query('*IDN?')

    def get_error(self):
        return self.query('SYST:ERR?')

    def clear_error(self):
        self.write('SYST:ERR:CLE')


#------------------------------------------------------------------------------------------------------------
    # --- 出力端子の切り替え FRONT / REAR ---
    def set_output_terminal(self, position: str):
        """
        出力端子の位置を設定します。
        position: 'FRONT' または 'REAR'
        """
        position = position.upper()
        if position not in ['FRONT', 'REAR']:
            raise ValueError("position must be 'FRONT' or 'REAR'")
        self.write(f'ROUT:TERM {position}')

    def get_output_terminal(self) -> str:
        """
        現在の出力端子の位置（FRONT または REAR）を返します。
        """
        return self.query('ROUT:TERM?').strip().upper()

    def set_mode(self, mode: str):
        mode = mode.upper()
        if mode not in ['VOLTAGE', 'CURRENT']:
            raise ValueError("Mode must be 'VOLTAGE' or 'CURRENT'")
        self.write(f'SOUR:FUNC:MODE {mode}')

    def get_mode(self) -> str:
        return self.query('SOUR:FUNC:MODE?')
    
    def set_voltage(self, voltage: float):
        self.write(f'SOUR:VOLT {voltage:.6f}')

    def get_voltage(self) -> float:
        return float(self.query('SOUR:VOLT?'))

    def set_current_mA(self, current: float):
        current_mA = 0.001 * current
        self.write(f'SOUR:CURR {current_mA:.6e}')

    def get_current_mA(self) -> float:
        return float(self.query('SOUR:CURR?'))*1000

    def set_shape(self, shape: str):
        shape = shape.upper()
        if shape not in ['DC', 'SIN']:
            raise ValueError("Shape must be 'DC' or 'SIN'")
        self.write(f'SOUR:FUNC {shape}')

    def get_shape(self) -> str:
        return self.query('SOUR:FUNC?')

    def set_frequency(self, frequency: float):
        self.write(f'SOUR:FREQ {frequency:.6f}')

    def get_frequency(self) -> float:
        return float(self.query('SOUR:FREQ?'))
    
    # --- 交流信号のオフセット（電流） ---
    def set_current_offset(self, offset: float):
        """
        AC電流出力のオフセット（DCバイアス）を設定します。
        単位: A
        """
        self.write(f'SOUR:CURR:OFFS {offset:.6e}')

    def get_current_offset(self) -> float:
        """
        現在のAC電流出力のオフセット（DCバイアス）を取得します。
        単位: A
        """
        return float(self.query('SOUR:CURR:OFFS?'))

    # --- 交流信号のオフセット（電圧） ---
    def set_voltage_offset(self, offset: float):
        """
        AC電圧出力のオフセット（DCバイアス）を設定します。
        単位: V
        """
        self.write(f'SOUR:VOLT:OFFS {offset:.6f}')

    def get_voltage_offset(self) -> float:
        """
        現在のAC電圧出力のオフセット（DCバイアス）を取得します。
        単位: V
        """
        return float(self.query('SOUR:VOLT:OFFS?'))


    # --- 位相設定 ---
    def set_phase(self, phase_deg: float):
        """
        出力信号の位相を設定します。
        範囲: -180 ～ +180 度
        """
        if not -180.0 <= phase_deg <= 180.0:
            raise ValueError("Phase must be between -180 and 180 degrees.")
        self.write(f'SOUR:PHAS {phase_deg:.3f}')

    def get_phase(self) -> float:
        """
        現在の出力信号の位相（度）を取得します。
        """
        return float(self.query('SOUR:PHAS?'))
    
    # --- トリガー遅延の設定（ミリ秒単位） ---
    def set_trigger_delay(self, delay_ms: int):
        """
        トリガー出力の遅延時間を設定します（単位: ミリ秒）。
        範囲：1 ～ 1,000,000 ms
        """
        if not (1 <= delay_ms <= 1_000_000):
            raise ValueError("Trigger delay must be between 1 and 1,000,000 milliseconds.")
        self.write(f'TRIG:SEQ:SRCD {delay_ms}')

    def get_trigger_delay(self) -> int:
        """
        現在のトリガー出力遅延時間（ミリ秒）を取得します。
        """
        return int(self.query('TRIG:SEQ:SRCD?'))



    def output_ON(self):
        self.write(f'OUTP:STAT 1')

    def output_OFF(self):
        self.write(f'OUTP:STAT 0')

    def output_check(self) -> bool:
        return self.query('OUTP:STAT?').strip() == '1'
    
    # --- 電圧リミット設定 ------------------------------------------------------------------------
    def set_voltage_limit(self, limit: float):
        self.write(f'SOUR:VOLT:LIM {limit:.6f}')

    def get_voltage_limit(self) -> float:
        return float(self.query('SOUR:VOLT:LIM?'))

    # --- 電流リミット設定 ------------------------------------------------------------------------
    def set_current_limit(self, limit: float):
        self.write(f'SOUR:CURR:LIM {limit:.6f}')

    def get_current_limit(self) -> float:
        return float(self.query('SOUR:CURR:LIM?'))

    # --- 電圧/電流レンジ設定 ------------------------------------------------------------------------
    def set_voltage_range(self, range_value: float):
        self.write(f'SOUR:VOLT:RANG {range_value:.6f}')

    def get_voltage_range(self) -> float:
        return float(self.query('SOUR:VOLT:RANG?'))

    def set_current_range(self, range_value: float):
        self.write(f'SOUR:CURR:RANG {range_value:.6f}')

    def get_current_range(self) -> float:
        return float(self.query('SOUR:CURR:RANG?'))

    # --- オートレンジ ON/OFF ------------------------------------------------------------------------
    def enable_voltage_autorange(self, enable: bool):
        self.write(f'SOUR:VOLT:RANG:AUTO {1 if enable else 0}')

    def check_voltage_autorange(self) -> bool:
        return self.query('SOUR:VOLT:RANG:AUTO?').strip() == '1'

    def enable_current_autorange(self, enable: bool):
        self.write(f'SOUR:CURR:RANG:AUTO {1 if enable else 0}')

    def check_current_autorange(self) -> bool:
        return self.query('SOUR:CURR:RANG:AUTO?').strip() == '1'

    # --- 電圧/電流コンプライアンス状態 ------------------------------------------------------------------------
    def check_voltage_compliance(self) -> bool:
        return self.query('SOUR:VOLT:PROT:TRIP?').strip() == '1'

    def check_current_compliance(self) -> bool:
        return self.query('SOUR:CURR:PROT:TRIP?').strip() == '1'
    
    # --- 電流ソースのコンプライアンス電圧（保護電圧） -------------------------------------------------------------
    def set_current_compliance_voltage(self, voltage: float):
        """
        電流出力時のコンプライアンス（最大許容）電圧を設定します。
        範囲：1 V ～ 100 V
        """
        self.write(f'SOUR:CURR:PROT {voltage:.6f}')

    def get_current_compliance_voltage(self) -> float:
        """
        現在の電流出力時のコンプライアンス電圧を取得します。
        """
        return float(self.query('SOUR:CURR:PROT?'))

    # --- 電圧ソースのコンプライアンス電流（保護電流） ---
    def set_voltage_compliance_current(self, current: float):
        """
        電圧出力時のコンプライアンス（最大許容）電流を設定します。
        範囲：100 nA ～ 100 mA
        """
        self.write(f'SOUR:VOLT:PROT {current:.6e}')

    def get_voltage_compliance_current(self) -> float:
        """
        現在の電圧出力時のコンプライアンス電流を取得します。
        """
        return float(self.query('SOUR:VOLT:PROT?'))


    # --- ステータスバイトの取得 ------------------------------------------------------------------------
    def read_status_byte(self) -> int:
        return int(self.query('*STB?'))

    # --- エラーキュー関連 ---
    def get_error_count(self) -> int:
        """
        エラーキューに溜まっているエントリ数を取得します。
        """
        return int(self.query('SYST:ERR:COUN?'))

    def get_next_error(self) -> tuple[int, str]:
        """
        次のエラーを取得し、キューから削除します。
        戻り値: (コード, メッセージ)
        """
        response = self.query('SYST:ERR:NEXT?').strip()
        code_str, message = response.split(',', 1)
        return int(code_str), message.strip('"')

    def get_all_errors(self) -> list[tuple[int, str]]:
        """
        すべてのエラーを取得し、キューを空にします。
        戻り値: [(コード, メッセージ), ...]
        """
        raw = self.query('SYST:ERR:ALL?').strip()
        if raw == '0,"No error"':
            return []
        parts = raw.split(',')
        return [(int(parts[i]), parts[i+1].strip('"')) for i in range(0, len(parts), 2)]


    #  測定関数----------------------------------------------------------------------------------------------------------------
    def AC_initialize(self, level: float, frequency: float, terminal: str="REAR"):
        
        self.logger.info("Starting AC initialization...")
        self.reset()
        self.set_mode('CURRENT')
        self.set_output_terminal(terminal)
        self.set_current_compliance_voltage(50)
        self.set_shape("SIN")
        self.set_frequency(frequency)
        self.set_current_mA(level)
        self.logger.info(f"AC initialization complete (level = {level} mA, freq = {frequency} Hz)")


    def Long_Wait(self, Waittime):
        NOW = datetime.now().strftime('%H時%M分%S秒')
        self.logger.info(f"待機時間: {Waittime}秒、開始時刻: {NOW}")
        time.sleep(Waittime)






def generate_current(start, end, step):
    current = [start + step * i for i in range(round((end - start) / step) + 1)]
    return current

def generate_Prime_num(f_min,f_max):
    return list(sympy.primerange(f_min,f_max))   



# In[ ]:


# import logging
# # from lakeshore155 import LakeShore155 

# Address = "TCPIP0::10.10.10.155::7777::SOCKET"

# # タイムスタンプ付きログ設定
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )
# logger = logging.getLogger("LakeshoreLogger")

# with LakeShore155(Address, logger=logger) as W155:
#     W155.reset()
#     W155.set_mode('CURRENT')
#     W155.set_output_terminal("REAR")
#     W155.set_current_compliance_voltage(50)
#     W155.set_shape("SIN")
#     W155.set_frequency(100)
#     W155.set_current(1e-4)
#     W155.output_ON()
#     time.sleep(3)
#     # W155.output_OFF()
#     # W155.close()


if __name__ =="__main__":

    with LakeShore155("TCPIP0::100.100.1.55::5025::SOCKET") as test:
        # output_On
        test.output_ON()
        print("output_On")
