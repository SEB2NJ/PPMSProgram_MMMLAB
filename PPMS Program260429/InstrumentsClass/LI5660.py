#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import atexit
import logging
import sys
import time
from datetime import datetime
from typing import Callable, List, Optional, Sequence, Tuple, Union, Literal, get_args, cast

import threading


import numpy as np
import pandas as pd
import pyvisa
from pyvisa import VisaIOError
from IPython.display import clear_output


LiteralTrigger = Literal["MAN", "EXT", "BUS"]
LiteralTerm1 = Literal["A", "AB", "C", "I", "HF"]
LiteralRoute2 = Literal["RINP", "IOSC", "SINP"]
LiteralRefType = Literal["SIN", "TPOS", "TNEG"]
LiteralDetMode = Literal["NORM", "HARM", "DUAL"]
LiteralFilterType = Literal["EXP", "MOV"]
LiteralDynRes = Literal["LOW", "MED", "HIGH"]
LiteralMeasMode = Literal["AUTO", "MANUAL", "USER", "INFO"]
TIME_CONSTANTS = [  1e-6, 2e-6, 5e-6,
                    1e-5, 2e-5, 5e-5,
                    1e-4, 2e-4, 5e-4,
                    1e-3, 2e-3, 5e-3,
                    1e-2, 2e-2, 5e-2,
                    1e-1, 2e-1, 5e-1,
                    1.0, 2.0, 5.0,
                    1e1, 2e1, 5e1,
                    1e2, 2e2, 5e2,
                    1e3, 2e3, 5e3,
                    1e4, 2e4, 5e4]

BUF_BITS = {1: 8, 2: 9, 3: 10}         # STAT:OPER:COND? のビット位置
BIT_WAITING_TRIGGER = 5
BIT_AUTO_RANGE_ADJ = 2

DATA_COLS = ["Status", "X", "Y", "R", "Theta", "Frequency"]  # 1,2,4,8,16,32 の和

class LI5600:
    # -------------------------- 基本I/Oとライフサイクル --------------------------
    def __init__(self, resource_name: str, logger: Optional[logging.Logger] = None, timeout: int = 10000,
                 enable_last_resort_reset: bool = True,
                 last_resort_reset_cmd: str = ":SYSTem:RST"):
        self._closed = False
        self.rm = pyvisa.ResourceManager()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False

        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = timeout
        self._resource_name = resource_name
        self._timeout = timeout
        self.inst.chunk_size = 1024 * 1024  # 1 MB
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self.inst.encoding = "ascii"
        self._io_lock = threading.RLock()          # ← 全I/O共通ロック
        self._drain_on_query = True                # ← 残骸ドレインを有効

        self.logger.debug(f"Connected to {resource_name}")
        atexit.register(self._cleanup)

        # 追加: 致命時のラストリゾート送信
        self.enable_last_resort_reset = enable_last_resort_reset
        self.last_resort_reset_cmd = last_resort_reset_cmd

    def __enter__(self):
        return self

    def __del__(self):
        self._cleanup()

    def __exit__(self, exc_type, exc_value, traceback):
        # ラストリゾート中は余計な問い合わせをしないで即クローズ
        if getattr(self, "_aborting", False):
            try:
                self.close()
            finally:
                return
        # ここではログだけ。プロセスは落とさない（上位でハンドリングしやすくする）
        # if exc_type is not None:
            # self.logger.error(f"Exception on exit: {exc_type.__name__}: {exc_value}")
        if exc_type is not None:
            self.logger.exception("Exception on exit", exc_info=True)  # ← traceback まで出す
        try:
            # 機器エラー確認
            err = self._query(":SYSTem:ERRor?", retry=10)
            if err and err != '0,"No error"':
                self.logger.warning(f"Instrument Error: {err}")
        except Exception as e:
            self.logger.error(f"Failed to query system error: {e}")
        # --- 追加: ローカルモードに戻す ---
        try:
            self.inst.write(":SYSTem:LOCal")
            self.logger.debug("Instrument set to LOCAL mode.")
        except Exception as e:
            self.logger.error(f"Failed to set LOCAL mode: {e}")
        self.close()


    def _cleanup(self):
        if not self._closed:
            try:
                self.close()
            except Exception:
                pass

    def close(self):
        self.logger.debug("Closing connection (LI5600)")
        try:
            self.inst.close()
        finally:
            self._closed = True

    def clear_log(self, update: bool = True):
        if update:
            try:
                clear_output(wait=True)
                self.logger.debug("セル出力をクリアしました")
            except Exception as e:
                self.logger.warning(f"clear_output に失敗: {e}")


    def _last_resort_reset_and_abort(self):
        if not (self.enable_last_resort_reset and self.last_resort_reset_cmd):
            return
        self.logger.warning(f"Last-resort: sending {self.last_resort_reset_cmd} (fire-and-forget) and aborting.")
        try:
            # 応答待ちなしで送る（終端は __init__ で設定済み）
            self.inst.write(self.last_resort_reset_cmd)
        except Exception as e:
            self.logger.error(f"Last-resort send failed: {e}")
        finally:
            # 以降のクリーンアップで計器に触らないようにする
            self._aborting = True
            try:
                self.close()
            except Exception:
                pass
            # ここで終了（__exit__ は呼ばれるが _aborting で即抜け）
            sys.exit(2)

    def _is_conn_lost(self, exc: Exception) -> bool:
        return isinstance(exc, VisaIOError) and getattr(exc, "error_code", None) == -1073807194

    def _open_new_session(self):
        # 既存rmを使う（rm自体が壊れているケースは稀）
        self.inst = self.rm.open_resource(self._resource_name)
        self.inst.timeout = self._timeout
        self.inst.chunk_size = 1024 * 1024
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"
        self._closed = False
        self.logger.debug(f"Reconnected to {self._resource_name}")

    def _reconnect(self, sleep_sec: float = 1.0):
        self.logger.warning("Connection lost. Reconnecting...")
        try:
            if getattr(self, "inst", None) is not None:
                try:
                    self.inst.close()
                except Exception:
                    pass
        finally:
            self._closed = True
        time.sleep(sleep_sec)
        self._open_new_session()


    # -------------------------- 内部ユーティリティ --------------------------
    @staticmethod
    def _is_bit_set(value: int, bit: int) -> bool:
        return bool(value & (1 << bit))

    @staticmethod
    def _validate_buffer(buffer: int) -> None:
        if buffer not in (1, 2, 3):
            raise ValueError("buffer must be one of 1, 2, or 3")

    @staticmethod
    def _sleep(sec: float):
        if sec > 0:
            time.sleep(sec)

    # --- 受信残骸のドレイン（ソケット向け） ---
    def _drain(self, max_bytes: int = 1_000_000) -> int:
        total = 0
        # ドレインは短いタイムアウトに
        orig_to = self.inst.timeout
        self.inst.timeout = max(50, min(orig_to, 100))
        try:
            while True:
                try:
                    # 終端無視で生バイト吸い尽くす
                    chunk = self.inst.read_bytes(4096, break_on_termchar=False)
                    total += len(chunk)
                    if total >= max_bytes:
                        break
                except VisaIOError:
                    break
        finally:
            self.inst.timeout = orig_to
        if total:
            self.logger.debug(f"Drain: discarded {total} bytes of residual data")
        return total

    # --- 行（LF終端）を生バイトで読み切ってからdecodeする ---
    def _readline_raw(self) -> str:
        # read_termination に任せても良いが、ここでは安全のため raw→手動decode
        data = bytearray()
        while True:
            chunk = self.inst.read_bytes(1, break_on_termchar=False)
            if not chunk:
                break
            data += chunk
            if chunk == b'\n':  # LF終端
                break
        # CR/LF を右側だけ落とす（先頭は触らない）
        s = data.decode(self.inst.encoding, errors="replace")
        return s.rstrip('\r\n')

    # --- 共通ラッパ：書き込み（排他 & 任意の *OPC? 待ち） ---
    def _write(self, cmd: str, delay: float = 0.2, wait_opc: bool = True):
        with self._io_lock:
            self.logger.debug(f"Write: {cmd}")
            payload = f"{cmd}\n".encode(self.inst.encoding)
            self.inst.write_raw(payload)
            if delay > 0:
                time.sleep(delay)
            if wait_opc:
                self.wait_for_opc()

    # --- 共通ラッパ：問い合わせ（排他 & ドレイン & 自前read） ---
    def _query(self, cmd: str, pre_delay: float = 0.2, retry: int = 5) -> str:
        with self._io_lock:
            for attempt in range(1, retry + 1):
                try:
                    if self._drain_on_query:
                        self._drain()

                    if pre_delay > 0:
                        time.sleep(pre_delay)

                    self.logger.debug(f"Query: {cmd}")

                    payload = f"{cmd}\n".encode(self.inst.encoding)
                    self.inst.write_raw(payload)

                    # 読み取り（既存のメソッドを使用）
                    resp = self._readline_raw()

                    # NULL除去などは既存通り
                    resp = resp.replace("\x00", "").rstrip()

                    if resp != "":
                        self.logger.debug(f"Read: {resp}")
                        return resp

                    self.logger.warning(f"Empty response (attempt {attempt}/{retry})")

                except Exception as e:
                    self.logger.warning(f"Query unexpected error (attempt {attempt}/{retry}): {e}")

            # リトライ回数切れ
            self.logger.critical(f"No valid response after {retry} retries for '{cmd}'")
            if self.enable_last_resort_reset and self.last_resort_reset_cmd:
                self._last_resort_reset_and_abort()
            raise IOError(f"Query failed after {retry} retries: {cmd}")

    # --- *OPC? も排他の中で動くように（_query内からも呼ばれるのでOK） ---
    def wait_for_opc(self, delay: float = 0.2, interval: float = 0.5, max_attempts: int = 10):
        # ここで _io_lock を二重取得できるよう RLock にしてある
        self.logger.debug("Waiting for *OPC?")
        for attempt in range(1, max_attempts + 1):
            try:
                if self._query("*OPC?", pre_delay=delay, retry=10) == "1":
                    self.logger.debug(f"*OPC? succeeded on attempt {attempt}")
                    return
                self.logger.warning(f"*OPC? returned non-1 (attempt {attempt}/{max_attempts})")
            except Exception as e:
                self.logger.warning(f"*OPC? failed (attempt {attempt}/{max_attempts}): {e}")
            time.sleep(interval)
        self.logger.error(f"*OPC? failed after {max_attempts} attempts")
        raise IOError("*OPC? failed after multiple retries")

    # --- clear_status は“頻繁に呼ばない”方針へ ---
    def clear_status(self):
        try:
            # 本当に必要なときだけ使う（例：接続直後）
            self.inst.clear()
            self.logger.debug("inst.clear()")
        except Exception as e:
            if self._is_conn_lost(e):
                self.logger.warning("inst.clear() skipped due to lost connection")
            else:
                self.logger.warning(f"inst.clear() failed: {e}")



    # 値設定→取得→検証の共通関数
    def set_and_verify(
        self,
        setter: Callable[..., None],
        getter: Callable[..., Union[str, float, int, bool]],
        target: Union[str, float, int, bool],
        *args,
        name: str = "",
        retries: int = 10,
        delay: float = 0.2,
        tolerance: float = 1e-4,
    ):
        for i in range(1, retries + 1):
            setter(target, *args)  # target を先頭引数に統一
            self._sleep(delay)
            actual = getter(*args)
            self.logger.debug(f"{name} set→read: {target} -> {actual}")

            ok = False
            if isinstance(target, (int, float)) and isinstance(actual, (int, float)):
                ok = abs(float(actual) - float(target)) <= tolerance
            elif isinstance(target, str):
                ok = str(actual).strip().upper() == target.strip().upper()
            else:
                ok = actual == target

            if ok:
                return actual

            self.logger.warning(f"[Retry {i}] {name} mismatch: expected {target}, got {actual}")
        raise ValueError(f"[Fail] Failed to set {name} to {target} after {retries} attempts.")

    # -------------------------- 基本SCPI --------------------------
    def reset(self):
        self._write("*RST", delay=3.0)

    def get_id(self) -> str:
        return self._query("*IDN?")

    def set_remote(self):
        self._write(":SYSTem:REMote")

    def set_local(self):
        self._write(":SYSTem:LOCal")

    def measure_x(self) -> float:
        return float(self._query("FETCh?"))

    # -------------------------- 表示/フォーマット --------------------------
    def set_display_mode(self):
        # 確認手段がないため検証なし
        self._write(":DISPlay FINE")
        self._write(":CALCulate1:FORMat REAL")
        self._write(":CALCulate2:FORMat IMAG")
        self._write(":CALCulate3:FORMat MLIN")
        self._write(":CALCulate4:FORMat PHAS")

    def set_data_format_ascii(self, fmt: str = "ASC"):
        if fmt.upper() != "ASC":
            raise ValueError("Only 'ASC' is supported.")
        self._write(f":FORM {fmt}")

    def get_data_format_ascii(self) -> str:
        return self._query(":FORMat?").strip().upper()

    # -------------------------- DATA サブシステム --------------------------
    def Data_columns(self, status: int) -> List[str]:
        # status は feed のビット和（1,2,4,8,16,32）
        bits = format(status, "06b")[::-1]
        return [DATA_COLS[i] for i, b in enumerate(bits) if b == "1"]

    def get_data(self) -> List[float]:
        raw = self._query(":DATA:DATA?")
        return [float(x) for x in raw.split(",") if x]

    def set_data_timer(self, seconds: float):
        self._write(f":DATA:TIMer {seconds}")

    def get_data_timer(self) -> float:
        return float(self._query(":DATA:TIM?"))

    def enable_data_recording(self, enable: bool):
        self._write(f":DATA:FEED:CONTrol {'ON' if enable else 'OFF'}")

    # バッファ設定
    def set_data_feed(self, feed: int, buffer: int):
        if buffer not in (1, 2, 3):
            raise ValueError("buffer must be 1, 2, or 3")
        if not (1 <= feed <= 62):
            raise ValueError("feed must be 1--62")
        self._write(f":DATA:FEED BUF{buffer}, {feed}", delay=1.0)
        self.logger.debug(f"Buffer{buffer} Feed ({feed}) -> {self.Data_columns(feed)}")

    def get_data_feed(self, buffer: int) -> int:
        self._validate_buffer(buffer)
        return int(self._query(f":DATA:FEED? BUF{buffer}"))

    def set_data_feed_control(self, mode: Literal["ALW", "NEV"], buffer: int):
        self._validate_buffer(buffer)
        if mode.upper() not in ("ALW", "NEV"):
            raise ValueError("mode must be 'ALW' or 'NEV'")
        self._write(f":DATA:FEED:CONTrol BUF{buffer}, {mode.upper()}", delay=1.0)

    def get_data_feed_control(self, buffer: int) -> str:
        self._validate_buffer(buffer)
        return self._query(f":DATA:FEED:CONTrol? BUF{buffer}")

    def set_data_points(self, points: int, buffer: int):
        self._validate_buffer(buffer)
        if buffer in (1, 2) and not (16 <= points <= 8192):
            raise ValueError("BUF1/2: 16--8192 points")
        if buffer == 3 and not (16 <= points <= 65536):
            raise ValueError("BUF3: 16--65536 points")
        self._write(f":DATA:POIN BUF{buffer}, {points}", delay=1.0)

    def get_data_points(self, buffer: int) -> int:
        self._validate_buffer(buffer)
        return int(self._query(f":DATA:POIN? BUF{buffer}"))

    def set_timer_status(self, enable: bool):
        self._write(f":DATA:TIM:STAT {'ON' if enable else 'OFF'}")

    def get_timer_status(self) -> bool:
        return self._query(":DATA:TIM:STAT?").strip() == "1"

    def get_buffer_count(self, buffer: int) -> int:
        self._validate_buffer(buffer)
        return int(self._query(f":DATA:COUNt? BUF{buffer}"))

    def delete_buffer_data(self, buffer: int):
        self._validate_buffer(buffer)
        self._write(f":DATA:DELete BUF{buffer}")

    def delete_all_buffer_data(self):
        self._write(":DATA:DELete:ALL", delay=1.0)

    def setup_buffer_recording(
        self,
        buffer: int,
        feed: int,
        points: int,
        timer: Optional[float] = None,
        continuous: Literal["ALW", "NEV"] = "ALW",
        check_parameter: bool = True,
    ):
        """
        代表的な設定をまとめて適用。旧実装の引数順バグ（feed/buffer逆）を修正。
        """
        self.logger.info(f"バッファ設定: Buffer{buffer}, Feed={feed}, Points={points}")
        if check_parameter:
            self.set_and_verify(self.set_data_feed, self.get_data_feed, feed, buffer, name=f"Buffer{buffer} Feed")
            self.set_and_verify(self.set_data_points, self.get_data_points, points, buffer, name=f"Buffer{buffer} Points")
            self.set_and_verify(self.set_data_feed_control, self.get_data_feed_control, continuous, buffer, name=f"Buffer{buffer} Feed Control")
            if timer is not None:
                self.set_and_verify(self.set_data_timer, self.get_data_timer, timer, name="Data Timer")
        else:
            # 正しい順序で呼ぶ（旧コードは逆順だった）
            self.set_data_feed(feed, buffer)
            self.set_data_points(points, buffer)
            self.set_data_feed_control(continuous, buffer)
            if timer is not None:
                self.set_data_timer(timer)

    def read_buffer_data(self,
        buffer: int,
        count: Optional[int] = None,
        start: int = 0,
        return_dataframe: bool = True,
        page_points: int = 100,   # 推奨既定値
        max_attempts: int = 3,    # 各ページの軽リトライ
    ):
        self._validate_buffer(buffer)
        if count is None:
            count = self.get_buffer_count(buffer)
        if count <= 0:
            raise ValueError("count must be > 0")

        # --- 1ページ目：列数を推定 ---
        first_pts = min(page_points, count)
        first_vals = None
        for attempt in range(1, max_attempts + 1):
            try:
                raw = self._query(f":DATA:DATA? BUF{buffer}, {first_pts}, {start}", pre_delay=0.2, retry=2)
                toks = [t.strip() for t in raw.strip().split(",") if t.strip() != ""]
                vals = [float(t) for t in toks]                 # 未完トークンがあればここで ValueError になる
                first_vals = vals
                break
            except Exception as e:
                self.logger.warning(f"First page read failed (attempt {attempt}/{max_attempts}): {e}")
                self.clear_status()
        if first_vals is None:
            raise IOError("Failed to read first page")
        if len(first_vals) % first_pts != 0:
            raise ValueError(f"Cannot infer column count from first page: tokens={len(first_vals)}, points={first_pts}")

        ncol = len(first_vals) // first_pts
        self.logger.debug(f"Detected {ncol} column(s) from first page")
        acc = first_vals[:]
        fetched_points = first_pts

        # --- 残りページ ---
        while fetched_points < count:
            take = min(page_points, count - fetched_points)
            page_vals = None
            for attempt in range(1, max_attempts + 1):
                try:
                    raw = self._query(f":DATA:DATA? BUF{buffer}, {take}, {start + fetched_points}", pre_delay=0.1, retry=2)
                    toks = [t.strip() for t in raw.strip().split(",") if t.strip() != ""]
                    vals = [float(t) for t in toks]  # ここで未完があれば即例外
                    page_vals = vals
                    break
                except Exception as e:
                    self.logger.warning(f"Page read failed (start={start + fetched_points}, attempt {attempt}/{max_attempts}): {e}")
                    self.clear_status()
            if page_vals is None:
                raise IOError(f"Failed to read page starting at point {fetched_points}")
            if len(page_vals) % ncol != 0:
                raise ValueError(f"Page misalignment at start={fetched_points}: tokens={len(page_vals)} not divisible by ncol={ncol}")
            acc.extend(page_vals)
            fetched_points += len(page_vals) // ncol

        expected_tokens = count * ncol
        if len(acc) != expected_tokens:
            raise ValueError(f"Incomplete/extra data: tokens={len(acc)} expected={expected_tokens}")
        if not return_dataframe:
            return acc

        arr = np.reshape(acc, (count, ncol))
        cols = [f"Col{i+1}" for i in range(ncol)]
        return pd.DataFrame(arr, columns=cols)



    def wait_for_buffer_full(self, buffer: int = 1, poll_interval: float = 1.0) -> bool:
        self._validate_buffer(buffer)
        self.logger.info("バッファ測定中... (buffer=%d)", buffer)
        while True:
            status = self.read_condition_value()
            self.logger.debug("Condition: 0b%s", format(status, "016b"))
            self.logger.debug("Decoded:\n%s", self.decode_condition(status))
            if self.is_buffer_full(buffer, status=status):
                self.logger.info("バッファ測定完了 (buffer=%d)", buffer)
                return True
            self._sleep(poll_interval)

    def is_buffer_full(self, buffer: int, status: Optional[int] = None) -> bool:
        self._validate_buffer(buffer)
        if status is None:
            status = self.read_condition_value()
        return self._is_bit_set(status, BUF_BITS[buffer])

    # -------------------------- ステータス --------------------------
    def read_condition_value(self) -> int:
        s = self._query(":STAT:OPER:COND?")
        try:
            return int(s)
        except ValueError:
            self.logger.error("条件レジスタの値が整数に変換できません: %r", s)
            raise

    def decode_condition(self, status: Optional[int] = None) -> str:
        if status is None:
            status = self.read_condition_value()
        labels = {
            15: "常に 0 (使用していません)",
            14: "常に 0 (使用していません)",
            13: "常に 0 (使用していません)",
            12: "外部基準信号 (10MHz) と同期が外れている",
            11: "常に 0 (使用していません)",
            10: "BUF3 が満杯",
            9:  "BUF2 が満杯",
            8:  "BUF1 が満杯",
            7:  "入力 DC オフセット自動調整中",
            6:  "常に 0 (使用していません)",
            5:  "トリガ待ち",
            4:  "タイマ測定中",
            3:  "常に 0 (使用していません)",
            2:  "自動レンジ選択機能でレンジとダイナミックリザーブを調整中",
            1:  "常に 0 (使用していません)",
            0:  "常に 0 (使用していません)",
        }
        on = [b for b in range(16) if (status >> b) & 1]
        return "\n".join(labels.get(b, f"Unknown bit {b}") for b in on)

    # -------------------------- ROUTe --------------------------
    def set_route_terminal(self, terminal: LiteralTerm1 | str) -> None:
        allowed = get_args(LiteralTerm1)  # ("A", "AB", "C", "I", "HF")
        t = str(terminal).upper()
        if t not in allowed:
            raise ValueError(f"terminal must be one of {allowed}")
        self._write(f":ROUTe {t}")

    def get_route_terminal(self) -> LiteralTerm1:
        allowed = get_args(LiteralTerm1)  # ("A", "AB", "C", "I", "HF")
        val = self._query(":ROUTe?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected ROUTe terminal value: {val!r}")
        return cast(LiteralTerm1, val)

    def set_route2_terminal(self, terminal: LiteralRoute2 | str) -> None:
        allowed = get_args(LiteralRoute2)  # ("RINP", "IOSC", "SINP")
        t = str(terminal).upper()
        if t not in allowed:
            raise ValueError(f"terminal must be one of {allowed}")
        self._write(f":ROUTe2 {t}")

    def get_route2_terminal(self) -> LiteralRoute2:
        allowed = get_args(LiteralRoute2)  # ("RINP", "IOSC", "SINP")
        val = self._query(":ROUTe2?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected ROUTe2 terminal value: {val!r}")
        return cast(LiteralRoute2, val)

    # -------------------------- SOURce --------------------------
    def set_source_frequency1(self, freq_hz: float):
        self._write(f":SOURce:FREQuency1 {freq_hz}")

    def get_source_frequency1(self) -> float:
        return float(self._query(":SOURce:FREQuency1?"))

    def set_source_frequency2(self, freq_hz: float):
        self._write(f":SOURce:FREQuency2 {freq_hz}")

    def get_source_frequency2(self) -> float:
        return float(self._query(":SOURce:FREQuency2?"))

    def set_internal_oscillator(self, source: str):
        s = str(source).upper()
        if s not in ("PRI", "SEC"):
            raise ValueError("source must be 'PRI' or 'SEC'")
        self._write(f":SOURce:IOSCillator {s}")

    def get_internal_oscillator(self) -> str:
        return self._query(":SOURce:IOSCillator?")

    def set_source_voltage_amplitude(self, volts: float):
        self._write(f":SOURce:VOLTage:LEVel:IMMediate:AMPLitude {volts}")

    def get_source_voltage_amplitude(self) -> float:
        return float(self._query(":SOUR:VOLT?"))

    def set_source_voltage_range(self, volts: float):
        self._write(f":SOURce:VOLTage:RANGe {volts}")

    def get_source_voltage_range(self) -> float:
        return float(self._query(":SOURce:VOLTage:RANGe?"))

    # -------------------------- INIT/Trigger --------------------------
    def set_continuous_mode(self, enable: bool):
        self._write(f":INIT:CONT {'ON' if enable else 'OFF'}")

    def is_continuous_mode(self) -> bool:
        return self._query(":INIT:CONT?") == "1"

    def start_measurement(self, retries: int = 5, per_try_timeout: float = 30.0, poll_interval: float = 1.0, settle_after: float = 0.0) -> bool:
        self.logger.info("トリガ待ちへ移行")
        for attempt in range(1, retries + 1):
            self.logger.debug("INIT 送信 (attempt %d/%d)", attempt, retries)
            self._write(":INIT", delay=2.0)
            start = time.monotonic()
            while True:
                st = self.read_condition_value()
                self.logger.debug("Condition: 0b%s", format(st, "016b"))
                self.logger.debug("Decoded:\n%s", self.decode_condition(st))
                if self._is_bit_set(st, BIT_WAITING_TRIGGER):
                    self.logger.debug("Trigger wait state entered.")
                    if settle_after:
                        self._sleep(settle_after)
                    return True
                if (time.monotonic() - start) >= per_try_timeout:
                    self.logger.warning("トリガ待ちに入らず。再送。")
                    break
                self._sleep(poll_interval)
        self.logger.error("INITを複数回送信したがトリガ待ちに移行できず。")
        return False

    def send_trigger(self):
        self._write("*TRG", delay=1.0)

    def set_trigger_delay(self, delay_s: float):
        if not (0 <= delay_s <= 100):
            raise ValueError("Trigger delay must be between 0 and 100 seconds.")
        self._write(f":TRIGger:DELay {delay_s}")

    def get_trigger_delay(self) -> float:
        return float(self._query(":TRIGger:DELay?"))

    def set_trigger_source(self, source: LiteralTrigger | str) -> None:
        # 許容値を Literal から実行時に取り出す（この関数内のみ有効スコープ）
        allowed = get_args(LiteralTrigger)  # ("MAN", "EXT", "BUS")

        s = str(source).upper()
        if s not in allowed:
            raise ValueError(f"Trigger source must be one of {allowed}")
        self._write(f":TRIGger:SOURce {s}")

    def get_trigger_source(self) -> LiteralTrigger:
        # 許容値を Literal から実行時に取り出す（この関数内のみ有効スコープ）
        allowed = get_args(LiteralTrigger)  # ("MAN", "EXT", "BUS")

        val = self._query(":TRIGger:SOURce?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected trigger source value: {val!r}")
        return cast(LiteralTrigger, val)

    def send_trigger_immediate(self, timeout: float = 60.0, poll_interval: float = 1.0, retries: int = 1) -> bool:
        self.logger.info("測定開始 (開始時刻: %s)", datetime.now().strftime("%H時%M分%S秒"))
        for attempt in range(1, retries + 1):
            self.logger.debug("Trigger送信 (attempt %d/%d)", attempt, retries)
            self.send_trigger()
            start = time.monotonic()
            while True:
                st = self.read_condition_value()
                self.logger.debug("Condition: 0b%s", format(st, "016b"))
                self.logger.debug("Decoded:\n%s", self.decode_condition(st))
                if not self._is_bit_set(st, BIT_WAITING_TRIGGER):
                    self.logger.info("Trigger受理（トリガ待ち解除）")
                    return True
                # まだトリガ待ち → 3秒休んで再送
                elif self._is_bit_set(st, BIT_WAITING_TRIGGER):
                    self.logger.debug("Trigger再送")
                    self._sleep(3.0)
                    self.send_trigger()
                if (time.monotonic() - start) >= timeout:
                    self.logger.warning("Trigger待機がタイムアウト。再送。")
                    break
                self._sleep(poll_interval)
        self.logger.error("Trigger再送も失敗。")
        return False

    # -------------------------- INPut --------------------------
    def set_input_coupling(self, mode: Literal["AC", "DC"] = "DC"):
        self._write(f":INPut1:COUPling {mode.upper()}")

    def get_input_coupling(self) -> str:
        return self._query(":INPut1:COUPling?")

    def set_notch_filter(self, frequency: int = 50, enable: bool = True):
        if frequency not in (50, 60):
            raise ValueError("Notch frequency must be 50 or 60 Hz")
        self._write(f":INPut1:FILTer:NOTCh1:FREQuency {frequency}")
        # enable/disable は別API（set_notch_state）で管理

    def get_notch_filter_frequency(self) -> int:
        return int(self._query(":INPut1:FILTer:NOTCh1:FREQuency?"))

    def set_notch_state(self, state: Union[str, bool], notch_number: int):
        if notch_number not in (1, 2):
            raise ValueError("notch_number must be 1 or 2")
        v = "1" if (str(state).upper() == "ON" or state is True) else "0"
        self._write(f":INPut1:FILTer:NOTCh{notch_number}:STATe {v}")

    def get_notch_state(self, notch_number: int) -> str:
        if notch_number not in (1, 2):
            raise ValueError("notch_number must be 1 or 2")
        r = self._query(f":INPut1:FILTer:NOTCh{notch_number}:STATe?")
        return "ON" if r.strip() in ("1", "ON") else "OFF"

    def set_input_gain(self, gain_dB: float):
        self._write(f":INPut1:GAIN {gain_dB}")

    def set_input_impedance(self, impedance_ohm: float):
        if impedance_ohm not in (50, 1e6):
            raise ValueError("impedance must be 50 or 1e6")
        self._write(f":INPut1:IMPedance {int(impedance_ohm)}")

    def auto_offset(self, once_only: bool = True):
        self._write(":INPut1:OFFSet:AUTO:ONCE" if once_only else ":INPut1:OFFSet:AUTO", delay=1.0)

    def set_input_ground(self, state: Union[str, Literal["GRO", "FLO"]]):
        s = str(state).upper()
        if s not in ("GRO", "FLO"):
            raise ValueError("Input ground must be 'GRO' or 'FLO'")
        self._write(f":INPut1:LOW {s}")

    def get_input_ground(self) -> str:
        return self._query(":INPut1:LOW?")

    def set_reference_type(self, ref_type: LiteralRefType | str = "SIN") -> None:
        allowed = get_args(LiteralRefType)  # ("SIN", "TPOS", "TNEG")
        s = str(ref_type).upper()
        if s not in allowed:
            raise ValueError(f"ref_type must be one of {allowed}")
        self._write(f":INPut2:TYPE {s}", delay=1)

    def get_reference_type(self) -> LiteralRefType:
        allowed = get_args(LiteralRefType)  # ("SIN", "TPOS", "TNEG")
        val = self._query(":INPut2:TYPE?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected INPut2:TYPE value: {val!r}")
        return cast(LiteralRefType, val)

    # -------------------------- SENSe --------------------------
    def set_auto_sense_once(self):
        self._write(":SENSe:AUTO:ONCE", delay=1)

    def set_data_selection(self, value: int):
        self._write(f":DATA {value}")

    def set_current_range(self, value: Optional[float] = None, auto: bool = False):
        if auto:
            self._write(":SENSe:CURRent1:AC:RANGe:AUTO", delay=1)
        elif value is not None:
            self._write(f":SENSe:CURRent1:AC:RANGe:UPPer {value}")
        else:
            raise ValueError("You must specify a value unless auto=True")

    def set_voltage_range(self, value: Optional[float] = None, auto: bool = False):
        if auto:
            self._write(":SENSe:VOLTage1:AC:RANGe:AUTO:ONCE", delay=1.0)
        elif value is not None:
            self._write(f":SENSe:VOLTage1:AC:RANGe:UPPer {value}")
        else:
            raise ValueError("You must specify a value unless auto=True")

    def set_phase(self, degrees: float):
        self._write(f":SENSe:PHASe1 {degrees}")

    def get_phase(self) -> float:
        return float(self._query(":SENSe:PHASe1?"))

    def auto_phase(self):
        self._write(":SENSe:PHASe1:AUTO:ONCE", delay=1.0)

    def set_detector_mode(self, mode: LiteralDetMode | str = "NORM") -> None:
        allowed = get_args(LiteralDetMode)  # ("NORM", "HARM", "DUAL")
        m = str(mode).upper()
        if m not in allowed:
            raise ValueError(f"mode must be one of {allowed}")
        self._write(f":SENSe:DETector:FUNCtion {m}")

    def get_detector_mode(self) -> LiteralDetMode:
        allowed = get_args(LiteralDetMode)  # ("NORM", "HARM", "DUAL")
        val = self._query(":SENSe:DETector:FUNCtion?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected detector mode value: {val!r}")
        return cast(LiteralDetMode, val)

    def get_frequency(self) -> float:
        return float(self._query(":SENSe:FREQuency1?"))

    def set_dynamic_reserve(self, mode: LiteralDynRes | str) -> None:
        # 実行時の許容値を Literal から抽出（この関数内に限定）
        allowed = get_args(LiteralDynRes)  # ("LOW", "MED", "HIGH")
        m = str(mode).upper()
        if m not in allowed:
            raise ValueError(f"Dynamic Reserve must be one of {allowed}")
        self._write(f":SENSe:DREServe {m}")

    def get_dynamic_reserve(self) -> LiteralDynRes:
        # 実行時の許容値を Literal から抽出（この関数内に限定）
        allowed = get_args(LiteralDynRes)  # ("LOW", "MED", "HIGH")
        val = self._query(":SENSe:DREServe?").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected Dynamic Reserve value: {val!r}")
        return cast(LiteralDynRes, val)

    def get_voltage_range(self) -> str:
        return float(self._query(":SENSe:VOLTage1:AC:RANGe:UPPer?"))

    # --- Harmonics ---
    def set_harmonic_measurement(self, enable: bool):
        self._write(f":SENSe:FREQuency1:HARMonics {'ON' if enable else 'OFF'}")

    def get_harmonic_measurement(self) -> bool:
        return self._query(":SENSe:FREQuency1:HARMonics?") == "1"

    def set_harmonic_multiplier(self, value: int):
        if not (1 <= value <= 63):
            raise ValueError("Harmonic multiplier must be 1..63")
        self._write(f":SENSe:FREQuency1:MULTiplier {value}", delay=3)

    def get_harmonic_multiplier(self) -> int:
        return int(self._query(":SENSe:FREQuency1:MULTiplier?"))

    def set_subharmonic_multiplier(self, value: int):
        if not (1 <= value <= 63):
            raise ValueError("Subharmonic multiplier must be 1..63")
        self._write(f":SENSe:FREQuency1:SMULtiplier {value}")

    def get_subharmonic_multiplier(self) -> int:
        return int(self._query(":SENSe:FREQuency1:SMULtiplier?"))

    # --- Filter ---
    def set_filter_type(self, filter_type: LiteralFilterType | str = "MOV", channel: int = 1) -> None:
        # 互換性: 旧コードで (1, "MOV") の順で誤って呼ばれても自動補正
        if isinstance(filter_type, int) and isinstance(channel, str):
            channel, filter_type = filter_type, channel

        allowed = get_args(LiteralFilterType)  # ("EXP", "MOV")
        ft = str(filter_type).upper()
        if ft not in allowed:
            raise ValueError(f"filter_type must be one of {allowed}")
        self._write(f":SENSe:FILTer{channel}:LPASs:TYPE {ft}")

    def get_filter_type(self, channel: int = 1) -> LiteralFilterType:
        allowed = get_args(LiteralFilterType)  # ("EXP", "MOV")
        val = self._query(f":SENSe:FILTer{channel}:LPASs:TYPE?").replace("\x00", "").strip().upper()
        if val not in allowed:
            raise ValueError(f"Unexpected filter type value: {val!r}")
        return cast(LiteralFilterType, val)

    def set_filter_slope(self, channel: int = 1, slope: int = 6):
        if slope not in (6, 12, 18, 24):
            raise ValueError("slope must be 6, 12, 18, or 24")
        self._write(f":SENSe:FILTer{channel}:LPASs:SLOPe {slope}")

    def get_filter_slope(self, channel: int = 1) -> int:
        return int(self._query(f":SENSe:FILTer{channel}:LPASs:SLOPe?"))

    def set_filter_time_constant(self, seconds: Optional[float] = None, auto: bool = False, channel: int = 1):
        if auto:
            self._write(f":SENSe:FILTer{channel}:LPASs:AUTO:ONCE", delay=1.0)
            return

        if seconds is None:
            raise ValueError("You must specify seconds unless auto=True")

        # TIME_CONSTANTS のみ受け付ける
        if seconds not in TIME_CONSTANTS:
            raise ValueError(f"Invalid time constant {seconds}. Must be one of {TIME_CONSTANTS}")

        self._write(f":SENSe:FILTer{channel}:LPASs:TCONstant {seconds}")



    def get_filter_time_constant(self, channel: int = 1) -> float:
        return float(self._query(f":SENSe:FILTer{channel}:LPASs:TCONstant?"))

    # -------------------------- 測定用ユーティリティ --------------------------
    def log_elapsed_time(self, start_time: float, message: str = "Elapsed time") -> pd.DataFrame:
        elapsed = time.time() - start_time
        self.logger.debug(f"{message}: {elapsed:.3f} s")
        return pd.DataFrame([[elapsed]], columns=["elapse_time"])

    def initialize_instrument(
        self,
        check_parameter: bool = True,
        terminal: Union[str, LiteralTerm1] = "AB",
        Reference: Union[str, LiteralRoute2] = "RINP",
        RefType: Union[str, LiteralRefType] = "TPOS",
        Notch: Union[str, bool] = "ON",
        Filter: Union[str, LiteralFilterType] = "MOV",
        Ground: Union[str, Literal["GRO", "FLO"]] = "FLO",
    ):
        self.reset()
        self.clear_status()
        self.set_display_mode()

        if check_parameter:
            self.set_and_verify(self.set_data_timer, self.get_data_timer, 0.064, name="Data Timer")
            self.set_and_verify(self.set_timer_status, self.get_timer_status, True, name="Timer Status")
            self.set_and_verify(self.set_trigger_delay, self.get_trigger_delay, 0.1, name="Trigger Delay")
            self.set_and_verify(self.set_trigger_source, self.get_trigger_source, "BUS", name="Trigger Source")
            self.set_and_verify(self.set_data_format_ascii, self.get_data_format_ascii, "ASC", name="Data Format")
            self.set_and_verify(self.set_route_terminal, self.get_route_terminal, terminal, name="Route Terminal")
            self.set_and_verify(self.set_route2_terminal, self.get_route2_terminal, Reference, name="Route2 Terminal")
            self.set_and_verify(self.set_reference_type, self.get_reference_type, RefType, name="Reference Type")
            self.set_and_verify(self.set_input_coupling, self.get_input_coupling, "AC", name="Input Coupling")
            self.set_and_verify(self.set_notch_filter, self.get_notch_filter_frequency, 50, name="Notch Frequency")
            self.set_and_verify(self.set_notch_state, self.get_notch_state, Notch, 1, name="Notch1 State")
            self.set_and_verify(self.set_notch_state, self.get_notch_state, Notch, 2, name="Notch2 State")
            self.set_and_verify(self.set_filter_type, self.get_filter_type, Filter, 1, name="Filter Type")
            self.set_and_verify(self.set_input_ground, self.get_input_ground, Ground, name="Input Ground")
            self.set_and_verify(self.set_phase, self.get_phase, 0.0, name="Phase")
            self.set_and_verify(self.set_harmonic_measurement, self.get_harmonic_measurement, True, name="Harmonic Mode")
            self.set_and_verify(self.set_harmonic_multiplier, self.get_harmonic_multiplier, 1, name="Harmonic Multiplier")
        else:
            self.set_data_timer(0.064)
            self.set_timer_status(True)
            self.set_trigger_delay(0.1)
            self.set_trigger_source("BUS")
            self.set_display_mode()
            self.set_data_format_ascii()
            self.set_route_terminal(terminal)
            self.set_route2_terminal(Reference)
            self.set_reference_type(RefType)
            self.set_input_coupling("AC")
            self.set_notch_filter(50)
            self.set_notch_state(True, 1)
            self.set_notch_state(True, 2)
            self.set_filter_type(Filter, 1)   # 引数順OK
            self.set_input_ground(Ground)
            self.set_phase(0.0)
            self.set_harmonic_measurement(True)
            self.set_harmonic_multiplier(1)

    def ask_frequency(self) -> float:
        self.set_data_selection(32)  # FREQ
        resp = self._query(":FETCH?")
        try:
            f = float(resp)
            self.logger.info(f"周波数: {f}")
            return f
        except ValueError:
            self.logger.error(f"Failed to parse frequency from response: '{resp}'")
            raise

    def Ask_lockin_parameters(self) -> pd.DataFrame:
        self.logger.info("-----測定パラメータ取得中-----")
        data = {
            "DynamicReserve": self.get_dynamic_reserve(),
            "FilterSlope": self.get_filter_slope(),
            "TimeConstant": self.get_filter_time_constant(),
            "VoltageRange": self.get_voltage_range(),
            "Phase": self.get_phase(),
        }
        return pd.DataFrame([data])

    def wait_for_auto_range_complete(self, timeout: float = 60.0, poll_interval: float = 1.0, settle_after: float = 3.0) -> bool:
        self.logger.debug("----- オートレンジ測定中 -----")
        start = time.monotonic()
        while True:
            st = self.read_condition_value()
            self.logger.debug("Condition: 0b%s", format(st, "016b"))
            self.logger.debug("Decoded:\n%s", self.decode_condition(st))
            if not self._is_bit_set(st, BIT_AUTO_RANGE_ADJ):
                self.logger.debug("自動レンジ選択完了")
                if settle_after:
                    self._sleep(settle_after)
                return True
            if (time.monotonic() - start) >= timeout:
                self.logger.warning("Timeout while waiting for auto range selection to complete.")
                return False
            self._sleep(poll_interval)

    def Auto_sense_phase0(self):
        self.set_auto_sense_once()
        self.wait_for_auto_range_complete()
        self.set_and_verify(self.set_phase, self.get_phase, 0.0, name="Phase")
        self.set_filter_time_constant(auto=True)
        self.wait_for_auto_range_complete()
        self.set_voltage_range(auto=True)
        self.wait_for_auto_range_complete()

    def _apply_manual_frontend(self, params: dict):
        """
        値の検証は一切行わず、 set_and_verify のみ呼ぶ。
        params は以下のキーを必須とする:
        - voltage_range, filter_slope, time_constant, dynamic_reserve, phase
        """
        required = ["voltage_range", "filter_slope", "time_constant", "dynamic_reserve", "phase"]
        missing = [k for k in required if k not in params]
        if missing:
            raise ValueError(f"_apply_manual_frontend requires all keys: {missing}")

        self.set_and_verify(self.set_dynamic_reserve, self.get_dynamic_reserve, params["dynamic_reserve"], name="Dynamic Reserve")
        self.set_and_verify(self.set_filter_slope, self.get_filter_slope, params["filter_slope"], name="Filter Slope")
        self.set_and_verify(
            lambda sec: self.set_filter_time_constant(seconds=sec, auto=False, channel=1),
            self.get_filter_time_constant,
            params["time_constant"],
            name="Time Constant",
        )
        self.set_and_verify(self.set_voltage_range, self.get_voltage_range, params["voltage_range"], name="Voltage Range")
        self.set_and_verify(self.set_phase, self.get_phase, params["phase"], name="Phase")


    def _extract_manual_params_for_harmonic(self, manual_dict: dict, harmonic: int) -> dict:
        """
        Manual_parameter から Harm{N}_ 接頭辞つきキーを取り出し、_apply_manual_frontend 用に整形して返す。
        必須キー: Harm{N}_DynamicReserve, Harm{N}_FilterSlope, Harm{N}_TimeConstant, Harm{N}_VoltageRange, Harm{N}_Phase
        """
        prefix = f"Harm{harmonic}_"
        key_map = {
            f"{prefix}DynamicReserve": "dynamic_reserve",
            f"{prefix}FilterSlope":    "filter_slope",
            f"{prefix}TimeConstant":   "time_constant",
            f"{prefix}VoltageRange":   "voltage_range",
            f"{prefix}Phase":          "phase",
        }
        missing = [k for k in key_map.keys() if k not in manual_dict]
        if missing:
            raise ValueError(f"Manual mode requires all parameters for Harm{harmonic}. Missing keys: {missing}")

        # 値の検証・型変換は行わず、そのまま渡す（set_and_verify に委ねる）
        return {dst: manual_dict[src] for src, dst in key_map.items()}


    def _extract_user_params_for_harmonic(self,
        source,                  # pd.DataFrame / pd.Series / dict
        harmonic: int,
        mode: LiteralMeasMode,   # "USER" or "INFO"
        frequency: Optional[float] = None,   # INFO の時に使用
    ):
        # --- 行の決定 ---
        if isinstance(source, pd.DataFrame):
            if mode == "INFO":
                # 最も近い frequency 行を選ぶ
                if "Frequency(Hz)" not in source.columns:
                    raise ValueError("INFO mode requires 'Frequency(Hz)' column in CSV.")
                diffs = (source["Frequency(Hz)"].astype(float) - float(frequency)).abs()
                row = source.loc[diffs.idxmin()]
            else:  # USER
                if len(source) == 0:
                    raise ValueError("USER mode received an empty DataFrame.")
                if len(source) > 1:
                    # どの行を使うか指定されていないので先頭行を採用（必要ならここを選択UIに）
                    self.logger.warning("USER mode received DataFrame with %d rows; using the first row (iloc[0]).", len(source))
                row = source.iloc[0]
        elif isinstance(source, pd.Series):
            row = source
        elif isinstance(source, dict):
            row = pd.Series(source)
        else:
            raise TypeError(f"Unsupported source type: {type(source)}")

        # --- 値取り出し（重複インデックスにも対応：先頭を採用） ---
        prefix = f"Harm{harmonic}_"
        def pick(name: str):
            if isinstance(row, pd.Series):
                sel = (row.index == name)
                return row[sel].iloc[0] if sel.any() else None
            return row.get(name, None)  # dict だった場合

        return {
            "dynamic_reserve": pick(f"{prefix}DynamicReserve"),
            "filter_slope":    pick(f"{prefix}FilterSlope"),
            "time_constant":   pick(f"{prefix}TimeConstant"),
            "voltage_range":   pick(f"{prefix}VoltageRange"),
            "phase":           pick(f"{prefix}Phase"),
        }




    def measure_data(self, data_selection: int) -> List[float]:
        self.set_data_selection(data_selection)
        resp = self._query(":FETCH?")
        return [float(x) for x in resp.split(",") if x]

    def analyze_buffer_data(self, buffer: int = 1, points: int = 50, feed: int = 31) -> pd.DataFrame:
        self.setup_buffer_recording(buffer=buffer, feed=feed, points=points)
        self.start_measurement()
        self.send_trigger_immediate()
        self.wait_for_buffer_full(buffer=buffer)

        df = self.read_buffer_data(buffer=buffer, count=points, return_dataframe=True)
        df.columns = self.Data_columns(feed)

        cols = list(df.columns)
        has_status = "Status" in cols
        has_freq = "Frequency" in cols
        value_cols = [c for c in cols if c not in ("Status", "Frequency")]

        parts: List[pd.DataFrame] = []

        if has_status:
            parts.append(pd.DataFrame({"Status": [df["Status"].max()]}))

        if value_cols:
            parts.append(df[value_cols].mean(numeric_only=True).to_frame().T.add_suffix("_mean"))
            parts.append(df[value_cols].std(numeric_only=True).to_frame().T.add_suffix("_std"))

        if has_freq:
            parts.append(pd.DataFrame({"Frequency_mean": [df["Frequency"].mean()]}))
            parts.append(pd.DataFrame({"Frequency_std": [df["Frequency"].std()]}))
        else:
            parts.append(pd.DataFrame({"Frequency": [self.get_frequency()]}))

        return pd.concat(parts, axis=1) if parts else pd.DataFrame()

    def harmonic_measurement(self,
        harmonic: int = 1,
        buffer: int = 1,
        points: int = 100,
        feed: int = 31,
        mode: LiteralMeasMode = "AUTO",
        Manual_parameter: Optional[object] = None,  # dict / pd.Series / pd.DataFrame / list[...] を許容
        frequency: Optional[float] = None,          # INFO のとき必須
    ):

        # 調和数は常に設定
        self.set_and_verify(self.set_harmonic_multiplier, self.get_harmonic_multiplier,
                            harmonic, name="Harmonic Multiplier")

        if mode == "AUTO":
            self.Auto_sense_phase0()

        elif mode == "MANUAL":
            if Manual_parameter is None:
                raise ValueError("MANUAL mode requires Manual_parameter dict (with HarmN_* keys).")
            p = self._extract_manual_params_for_harmonic(Manual_parameter, harmonic)
            # MANUAL は 5 項目必須（値検証はせず set_and_verify に委譲）
            required = ["dynamic_reserve", "filter_slope", "time_constant", "voltage_range", "phase"]
            missing = [k for k in required if (k not in p or p[k] is None)]
            if missing:
                raise ValueError(f"MANUAL: missing parameters for Harm{harmonic}: {missing}")
            self._apply_manual_frontend(p)

        else:
            # USER / INFO 共通フロー：まず抽出
            if Manual_parameter is None:
                raise ValueError(f"{mode} mode requires Manual_parameter (CSV row or table).")
            if mode == "INFO" and frequency is None:
                raise ValueError("INFO mode requires 'frequency' argument.")
            p = self._extract_user_params_for_harmonic(
                source=Manual_parameter,
                harmonic=harmonic,
                mode=mode,           # "USER" or "INFO"（INFOは Frequency(Hz) 最至近行を選択）
                frequency=frequency,
            )
            self.logger.debug(f"{mode} params for Harm{harmonic}: {p!r}")
            self._apply_manual_frontend(p)

        # AUTO / MANUAL / USER / INFO → いずれも測定して返す
        param = self.Ask_lockin_parameters().add_prefix(f"Harm{harmonic}_")
        out = self.analyze_buffer_data(buffer=buffer, points=points, feed=feed).add_prefix(f"Harm{harmonic}_")
        return param, out







    # def harmonic_measurement_loop(self,
    #     Harmonics: Sequence[int],
    #     Averaging: Sequence[int],
    #     start_time: float = 0.0,
    #     mode: LiteralMeasMode = "AUTO",
    #     Manual_parameter: Optional[object] = None,  # DataFrame / Series / dict
    #     frequency: Optional[float] = None,          # INFO のとき必須
    # ):
    #     if len(Harmonics) != len(Averaging):
    #         raise ValueError("Harmonics と Averaging の長さは一致している必要があります。")

    #     parameters = pd.DataFrame([])
    #     results = self.log_elapsed_time(start_time)

    #     for H, Ave in zip(Harmonics, Averaging):
    #         if mode == "INFO" and frequency is None:
    #             raise ValueError("INFO mode requires 'frequency' argument in loop.")

    #         param, out = self.harmonic_measurement(
    #             harmonic=H,
    #             buffer=1,
    #             points=Ave,
    #             feed=31,
    #             mode=mode,
    #             Manual_parameter=Manual_parameter,
    #             frequency=frequency,
    #         )
    #         param.insert(0, "Harmonic", H)
    #         param["Averaging"] = Ave
    #         if not out.empty:
    #             results = pd.concat([results, out], axis=1)
    #         parameters = pd.concat([parameters, param], axis=1)

    #     return results, parameters



    def harmonic_measurement_loop(
        self,
        Harmonics: Sequence[int],
        Averaging: Sequence[int],
        start_time: float = 0.0,
        mode: LiteralMeasMode = "AUTO",
        Manual_parameter: Optional[object] = None,  # DataFrame / Series / dict
        frequency: Optional[float] = None,          # INFO のとき必須
    ):
        if len(Harmonics) != len(Averaging):
            raise ValueError("Harmonics と Averaging の長さは一致している必要があります。")

        # mode要件チェックを先に集約
        if mode == "INFO" and frequency is None:
            raise ValueError("INFO mode requires 'frequency' argument.")
        if mode in ("USER", "INFO") and Manual_parameter is None:
            raise ValueError(f"{mode} mode requires 'Manual_parameter'.")

        # results: 基本列（elapsed等）＋各Hのoutを横結合
        base = self.log_elapsed_time(start_time)
        out_list = [base]          # DataFrameをリストに貯める
        param_list = []            # 各Hのparam（DataFrame）をリストに貯める

        for H, Ave in zip(Harmonics, Averaging):
            param, out = self.harmonic_measurement(
                harmonic=H,
                buffer=1,
                points=Ave,
                feed=31,
                mode=mode,
                Manual_parameter=Manual_parameter,
                frequency=frequency,
            )

            # param: “そのハーモニックの設定情報”として列を整形
            # （今の「横に並べる」仕様を維持するため、列名をHでユニーク化するのがおすすめ）
            # 例: paramが1行データフレーム想定
            param = param.copy()
            param.insert(0, "Harmonic", H)
            param["Averaging"] = Ave

            # ★衝突回避：param列名に suffix/prefix を付けておくと後で安全
            # 例: "Sensitivity" -> "Sensitivity_H1"
            param.columns = [f"{c}_H{H}" for c in param.columns]

            param_list.append(param)

            if out is not None and not out.empty:
                # out側も衝突するならここで out.add_prefix(f"H{H}_") など
                out_list.append(out)

        results = pd.concat(out_list, axis=1)
        parameters = pd.concat(param_list, axis=1) if param_list else pd.DataFrame()

        return results, parameters




    # -------------------------- 内部発振支援 --------------------------
    def set_IOSC_range(self, volt: float = 0.0) -> float:
        if volt <= 0.01:
            return 0.01
        if volt <= 0.1:
            return 0.1
        if volt <= 1.0:
            return 1.0
        raise ValueError("内部参照信号レンジError: 入力電圧が範囲外です。")

    def current_gain(self, current: float = 0.0, gain_mode: str = "HIGH") -> float:
        gm = gain_mode.upper()
        if gm == "HIGH":
            volt = current / 5
        elif gm == "LOW":
            volt = current / 0.05
        else:
            raise ValueError("ゲインモードは 'HIGH' または 'LOW'")
        if volt > 1.0:
            raise ValueError(f"Current Error: 計算電圧 {volt:.3f} V が最大値 1.0 V を超えています。")
        return round(volt, 3)

    def apply_current(self, current: float, frequency: float, gain_mode: str = "HIGH"):
        volt = self.current_gain(current, gain_mode)
        rang = self.set_IOSC_range(volt)
        self.set_and_verify(self.set_internal_oscillator, self.get_internal_oscillator, "PRI", name="Internal Oscillator")
        self.set_and_verify(self.set_source_frequency1, self.get_source_frequency1, frequency, name="Source Frequency1", tolerance=1.0)
        self.set_and_verify(self.set_source_voltage_range, self.get_source_voltage_range, rang, name="Source Voltage Range", tolerance=0.1)
        self.set_and_verify(self.set_source_voltage_amplitude, self.get_source_voltage_amplitude, volt, name="Source Voltage Amplitude", tolerance=0.01)
        self.logger.info(f"内部発振設定完了: {current*1000:.2f} mA, {frequency:.3f} Hz, (Gain: {gain_mode}, Volt: {volt:.3f} V, Range: {rang:.2f} V)")

    def current_off(self):
        self.set_source_voltage_amplitude(0.0)
        self.logger.info("Current OFF")

    def set_IOSC_Freq(self, frequency: float) -> float:
        return float(self.set_and_verify(self.set_source_frequency1, self.get_source_frequency1, frequency, name="Source Frequency1", tolerance=1.0))

    def Long_Wait(self, Waittime: float):
        self.logger.info(f"待機時間: {Waittime}秒、開始時刻: {datetime.now().strftime('%H時%M分%S秒')}")
        self._sleep(Waittime)


# In[ ]:


import threading
import queue
import pandas as pd
import time
from typing import Sequence, Optional

class NF_LI5660_Q:
    """
    複数台の NF_LI5600 を用いて harmonic 測定を並列実行する管理クラス
    """

    def __init__(
        self,
        visas: Sequence[str],
        logger,
        init_kwargs: dict,
        retry_wait: float = 10.0,
    ):
        if len(visas) < 1:
            raise ValueError("At least one VISA address is required.")

        self.visas = list(visas)
        self.logger = logger
        self.init_kwargs = init_kwargs
        self.retry_wait = retry_wait

    # ------------------------------------------------------------
    # 内部 worker
    # ------------------------------------------------------------
    def _worker(
        self,
        visa: str,
        instrument_id: int,
        task_q: queue.Queue,
        lock: threading.Lock,
        results: dict,
        params: dict,
        *,
        Harmonics,
        Averaging,
        start_time,
        mode,
        Manual_parameter,
        frequency,
    ):
        with NF_LI5600(visa, logger=self.logger) as li:
            li.initialize_instrument(**self.init_kwargs)

            while True:
                try:
                    i = task_q.get(block=False)
                except queue.Empty:
                    break

                H = Harmonics[i]
                Ave = Averaging[i]
                self.logger.info(f"[LI{instrument_id}] start H={H}")

                while True:
                    try:
                        param, out = li.harmonic_measurement(
                            harmonic=H,
                            buffer=1,
                            points=Ave,
                            feed=31,
                            mode=mode,
                            Manual_parameter=Manual_parameter,
                            frequency=frequency,
                        )

                        # ---- param 整形（あなたの仕様を踏襲）----
                        param = param.copy()
                        param.insert(0, "Harmonic", H)
                        param["Averaging"] = Ave
                        param.columns = [f"{c}_H{H}" for c in param.columns]

                        # out の prefix（必要なら）
                        # out = out.add_prefix(f"LI{instrument_id}_")

                        with lock:
                            results[H] = out
                            params[H] = param
                        break

                    except Exception as e:
                        self.logger.error(
                            f"[LI{instrument_id}] retry H={H}, f={frequency}: {e}"
                        )
                        time.sleep(self.retry_wait)

                task_q.task_done()

    # ------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------
    def measure(
        self,
        *,
        Harmonics: Sequence[int],
        Averaging: Sequence[int],
        start_time: float,
        mode: str = "AUTO",
        Manual_parameter: Optional[object] = None,
        frequency: Optional[float] = None,
    ):
        if len(Harmonics) != len(Averaging):
            raise ValueError("Harmonics and Averaging must have same length.")

        task_q = queue.Queue()
        for i in range(len(Harmonics)):
            task_q.put(i)

        lock = threading.Lock()
        results_dict = {}
        params_dict = {}

        threads = []
        for idx, visa in enumerate(self.visas, start=1):
            t = threading.Thread(
                target=self._worker,
                args=(visa, idx, task_q, lock, results_dict, params_dict),
                kwargs=dict(
                    Harmonics=Harmonics,
                    Averaging=Averaging,
                    start_time=start_time,
                    mode=mode,
                    Manual_parameter=Manual_parameter,
                    frequency=frequency,
                ),
                daemon=True,
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # ---- 結果復元（Harmonics順）----
        out_list = [results_dict[h] for h in Harmonics]
        Result = pd.concat(out_list, axis=1)

        param_list = [params_dict[h] for h in Harmonics]
        Parameters = pd.concat(param_list, axis=1) if param_list else pd.DataFrame()

        return Result, Parameters


# In[ ]:


# import logging
# # from NF_LI5600 import NF_LI5600 

# Address = "TCPIP0::10.10.10.101::5025::SOCKET"


# # タイムスタンプ付きログ設定
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )
# logger = logging.getLogger("Logger")

# start_time = time.time()
# Harmonics = [1,2,3]
# Averaging = [50, 50, 50]

# with NF_LI5600(Address) as LI5600:
#     LI5600.initialize_instrument()

#     #autorange
#     # LI5600.Auto_sense_phase0()

#     #単発測定
#     # Freq=LI5600.get_frequency()
#     # data=LI5600.measure_data(31)

#     #バッファ測定(調波)
#     # Harm = 3
#     # param, output=LI5600.harmonic_measurement(harmonic=Harm, buffer=1, points=100)

#     #loop
#     # Results, parameters = LI5600.harmonic_measurement_loop(Harmonics, Averaging, start_time)




# In[ ]:


# import logging
# # from lakeshore155 import LakeShore155 

# Address = "TCPIP0::10.10.10.101::5025::SOCKET"


# # タイムスタンプ付きログ設定
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )
# logger = logging.getLogger("Logger")

# with NF_LI5600(Address, logger=logger) as LI5600:
#     # LI5600.initialize_instrument()
#     #バッファ測定(調波)
#     # Harm = 1
#     # param, output=LI5600.harmonic_measurement(harmonic=Harm, buffer=1, points=300)
#     # LI5600.start_measurement()
#     # LI5600.send_trigger_immediate()

#     # def set_notch_state(self, notch_number: int, enable: bool):
#     #     """指定したノッチフィルタ（1または2）のON/OFFを設定"""
#     #     state = "ON" if enable else "OFF"
#     #     self.write_command(f":INPut1:FILTer:NOTCh{notch_number}:STATe {state}")


#     # def get_notch_state(self, notch_number: int) -> bool:
#     #     return self.query_command(f":INPut1:FILTer:NOTCh{notch_number}:STATe?").strip().upper() in ["1", "ON"]


#     # LI5600.set_notch_state(1, True)
#     # ans = LI5600.get_notch_state(1)
#     # LI5600.set_and_verify(LI5600.set_notch_state, LI5600.get_notch_state, 1, True, name="Notch1 State")  # 基本波ノッチON




# In[ ]:


# import logging
# from ADCMT3100 import ADCMT3100
# from W155_Socket import LakeShore155
# # from LI5660_Socket import NF_LI5600
# from W155_Socket import generate_current, generate_Prime_num
# from FileOperation import FileOperation, setup_logger
# FO = FileOperation()
# import time
# import pandas as pd
# import sys
# import os

# Filename, Infoname, Figname, Logname= FO.Make_file()

# # タイムスタンプ付きログ設定
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     datefmt="%Y-%m-%d %H:%M:%S"
# )
# logger = logging.getLogger("Logger")
# # ファイル出力（指定された場合）
# os.makedirs(os.path.dirname(Logname), exist_ok=True)
# file_handler = logging.FileHandler(Logname, encoding='utf-8')
# # file_handler.setFormatter(format)
# logger.addHandler(file_handler)

# W155_VISA = "TCPIP0::10.10.10.155::7777::SOCKET"
# LI5660_VISA = "TCPIP0::10.10.10.101::5025::SOCKET"


# # タイムスタンプ付きログ設定
# # logger = setup_logger(log_file=Logname) 
# # LI_logger = setup_logger(log_file=Logname, logger_name="LI5600")
# # LS_logger = setup_logger(log_file=Logname, logger_name="LakeShore155")
# #*************************************************************************************************
# level = 0.1    # mA
# frequency = 11  # Hz
# Harmonics = [1,2,3]
# Averaging = [50,1000,1000]
# frequency_list = generate_Prime_num(frequency, 10000)
# Waittime     = [10     for i in range(len(frequency_list ))]      # sec
# terminal = "FRONT"  #"REAR" or "FRONT"
# #*************************************************************************************************

# start_time = time.time()
# Data = pd.DataFrame([]); Info = pd.DataFrame([])


# with NF_LI5600(LI5660_VISA, logger=logger) as LI5600:
#     LI5600.initialize_instrument(terminal= "AB", Reference= "IOSC", RefType = "TPOS", Notch ="OFF", Filter ="MOV", Ground = "FLO")
#     LI5600.apply_current(level, frequency, "HIGH")
#     LI5600.Long_Wait(30)
# for i, frequency in enumerate(frequency_list):
#     with NF_LI5600(LI5660_VISA, logger=logger) as LI5600:
#         LI5600.clear_log()
#         Freq = LI5600.set_IOSC_Freq(frequency)
#         Freq_pd = pd.DataFrame([Freq], columns=["Frequency(Hz)"])
#         LI5600.Long_Wait(Waittime[i])

#     while True:
#         try:
#             with NF_LI5600(LI5660_VISA, logger=logger) as LI5600:
#                 # LI5600.apply_current(level, frequency, "HIGH")
#                 Result, parameters = LI5600.harmonic_measurement_loop(Harmonics, Averaging, start_time)
#                 Results = pd.concat([Freq_pd, Result], axis=1)
#                 Data    = pd.concat([Data, Results], ignore_index=True)
#                 Info    = pd.concat([Info, parameters], ignore_index=True)

#                 fig = FO.plot_figure(Data, Harmonics)
#                 fig.savefig(Figname)
#                 FileOperation.SaveFile(Data, Filename)
#                 FileOperation.SaveFile(Info, Infoname)
#                 break  # 成功したのでループを抜ける

#         except IOError as e:
#                 logger.critical(f"IOError at index {i}, freq={frequency}: {e}")
#                 LI5600.current_off()
#                 sys.exit(1)

#         except Exception as e:
#             logger.error(f"LI5600 measurement failed at index {i} (Frequency = {frequency}): {e}")
#             time.sleep(10)  # 少し待ってから再試行

# LI5600.current_off()

# display(Data)


# In[ ]:


if __name__ =="__main__":
    pd.set_option('display.max_columns', None)

    pd.set_option('display.max_rows', None)

    pd.set_option('display.width', 1000)

    pd.set_option('display.max_colwidth', None)
    LI5660_VISA = "TCPIP0::100.100.1.55::5025::SOCKET"
    LI5660_VISA2 = "TCPIP0::100.100.1.56::5025::SOCKET"
    testInstance = LI5600(LI5660_VISA)
    testInstance2 = LI5600(LI5660_VISA2)

    result, parameter = testInstance.harmonic_measurement_loop(Harmonics=[1], Averaging=[100])
    result2, parameter2 = testInstance2.harmonic_measurement_loop(Harmonics=[2], Averaging=[100])

    print(f"result: {result}, parameter: {parameter}")
    print(f"result: {result2}, parameter: {parameter2}")