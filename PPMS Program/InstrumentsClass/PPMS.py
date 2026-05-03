#!/usr/bin/env python
# coding: utf-8

# In[ ]:


from __future__ import annotations

import time
import logging
from typing import Optional, Tuple
from typing import List
import numpy as np

import MultiPyVu as mpv


class PPMS:
    """
    MultiPyVu を使って PPMS / MultiVu を操作するためのラッパークラス。

    主な機能:
      - Server / Client の開始と終了
      - 磁場設定・取得
      - 温度設定・取得
      - Rotator 角度設定・取得
      - He level 取得（client.get_level() が使える環境向け）
      - logging 出力
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5000,
        start_server: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.start_server = start_server

        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False

        self.server = None
        self.client = None
        self._connected = False

    # =========================
    # context manager
    # =========================
    def __enter__(self) -> "PPMSController":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    # =========================
    # connection
    # =========================
    def open(self) -> None:
        """Server / Client を開始して接続する。"""
        if self._connected:
            self.logger.debug("PPMSController is already connected.")
            return

        try:
            if self.start_server:
                self.logger.debug("Starting MultiPyVu Server...")
                self.server = mpv.Server()
                self.server.__enter__()
                self.logger.info("MultiPyVu Server started.")

            self.logger.debug(f"Connecting MultiPyVu Client to {self.host}:{self.port} ...")
            self.client = mpv.Client(host=self.host, port=self.port)
            self.client.__enter__()
            self._connected = True
            self.logger.info(f"Connected to MultiPyVu Client ({self.host}:{self.port}).")

        except Exception as e:
            self.logger.exception(f"Failed to open PPMSController: {e}")
            self.close()
            raise

    def close(self) -> None:
        """Client / Server を終了する。"""
        if self.client is not None:
            try:
                self.client.__exit__(None, None, None)
                self.logger.info("MultiPyVu Client closed.")
            except Exception as e:
                self.logger.exception(f"Error while closing client: {e}")
            finally:
                self.client = None

        if self.server is not None:
            try:
                self.server.__exit__(None, None, None)
                self.logger.info("MultiPyVu Server closed.")
            except Exception as e:
                self.logger.exception(f"Error while closing server: {e}")
            finally:
                self.server = None

        self._connected = False

    def _require_client(self):
        if not self._connected or self.client is None:
            raise RuntimeError("PPMSController is not connected. Call open() first or use with PPMSController(...).")

    # =========================
    # common helpers
    # =========================
    def wait_for_stable(
        self,
        delay_sec: float = 10.0,
        wait_temperature: bool = True,
        wait_field: bool = True,
    ) -> None:
        """
        温度・磁場の安定待ち
        """

        timeout_sec = 0
        self._require_client()

        bitmask = 0
        targets = []

        if wait_temperature:
            bitmask |= self.client.temperature.waitfor
            targets.append("Temperature")

        if wait_field:
            bitmask |= self.client.field.waitfor
            targets.append("Field")

        # ===== 何も待たない場合 =====
        if bitmask == 0:
            self.logger.warning("wait_for_stable called but nothing to wait for.")
            return

        # ===== ログ =====
        target_str = " & ".join(targets)
        self.logger.info(
            f"Waiting for {target_str} stability (delay={delay_sec}s)"
        )

        # ===== wait =====
        self.client.wait_for(delay_sec, timeout_sec=timeout_sec, bitmask=bitmask)

        self.logger.info(f"{target_str} stabilization completed.")

    # =========================
    # field
    # =========================
    def set_field(
        self,
        target_oe: float,
        rate_oe_per_sec: float = 100.0,
        approach_mode=None,
        field_mode=None,
        wait: bool = True,
        delay_sec: float = 10.0,
    ) -> float:

        self._require_client()

        rate_min = 1.0
        rate_max = 100.0

        original_rate = rate_oe_per_sec
        rate_oe_per_sec = max(rate_min, min(rate_max, rate_oe_per_sec))

        if rate_oe_per_sec != original_rate:
            self.logger.warning(
                f"Field rate clipped: {original_rate} → {rate_oe_per_sec} Oe/s "
                f"(allowed range: {rate_min}-{rate_max})"
            )

        Amode = str(approach_mode).strip().lower() if approach_mode is not None else None

        if Amode is None or Amode == "linear":
            approach_mode = self.client.field.approach_mode.linear
        elif Amode in ("no_overshoot", "noovershoot"):
            approach_mode = self.client.field.approach_mode.no_overshoot
        elif Amode == "oscillate":
            approach_mode = self.client.field.approach_mode.oscillate
        else:
            raise ValueError(
                "approach_mode must be None, 'linear', 'no_overshoot', or 'oscillate'"
            )

        # ===== field_mode =====
        Fmode = str(field_mode).strip().lower() if field_mode is not None else None

        if Fmode is None or Fmode == "persistent":
            field_mode = self.client.field.driven_mode.persistent
        elif Fmode == "driven":
            field_mode = self.client.field.driven_mode.driven
        else:
            raise ValueError(
                "field_mode must be None, 'persistent', or 'driven'"
            )

        self.logger.info(
            f"Set field: {target_oe} Oe"
        )
        self.client.set_field(target_oe, rate_oe_per_sec, approach_mode, field_mode)

        if wait:
            self.wait_for_stable(
                delay_sec=delay_sec,
                wait_temperature=False,
                wait_field=True,
            )

        field, _ = self.get_field()
        return field

    def get_field(self) -> Tuple[float, str]:
        """現在磁場を取得。"""
        self._require_client()
        field, status = self.client.get_field()
        self.logger.info(f"Current field: {field} Oe, status={status}")
        return field, status

    # =========================
    # temperature
    # =========================
    def set_temperature(
        self,
        target_k: float,
        rate_k_per_min: float = 10.0,
        approach_mode=None,
        wait: bool = True,
        delay_sec: float = 10.0,
    ) -> float:
        self._require_client()

        if approach_mode is None:
            approach_mode = self.client.temperature.approach_mode.fast_settle

        self.logger.info(
            f"Set temperature: target={target_k} K, rate={rate_k_per_min} K/min, "
            f"approach_mode={approach_mode}"
        )
        self.client.set_temperature(target_k, rate_k_per_min, approach_mode)

        if wait:
            self.wait_for_stable(
                delay_sec=delay_sec,
                wait_temperature=True,
                wait_field=False,
            )

        temperature, _ = self.get_temperature()
        return temperature

    def get_temperature(self) -> Tuple[float, str]:
        """現在温度を取得。"""
        self._require_client()
        temperature, status = self.client.get_temperature()
        self.logger.info(f"Current temperature: {temperature} K, status={status}")
        return temperature, status

    # =========================
    # rotator
    # =========================
    def set_position(
        self,
        target_deg: float,
        poll_interval_sec: float = 1.0,
        wait: bool = True,
        stop_status: str = "Transport stopped at set point",
    ) -> float:
        speed_index: int = 1
        self._require_client()

        deg_min = -5.0
        deg_max = 362.0

        original_deg = target_deg
        target_deg = max(deg_min, min(deg_max, target_deg))

        if target_deg != original_deg:
            self.logger.warning(
                f"Rotator angle clipped: {original_deg} → {target_deg} deg "
                f"(allowed range: {deg_min}–{deg_max})"
            )

        self.logger.info(f"Set rotator position: {target_deg} deg")
        self.client.set_position(target_deg, speed_index)

        if not wait:
            pos, _ = self.get_position()
            return pos

        while True:
            pos, status = self.get_position()
            self.logger.debug(f"Rotator moving: pos={pos}, status={status}")

            if status == stop_status:
                break

            time.sleep(poll_interval_sec)

        self.logger.info(f"Rotator reached: {pos} deg")
        return pos

    def get_position(self) -> Tuple[float, str]:
        """現在の Rotator 位置を取得。"""
        self._require_client()
        pos, status = self.client.get_position()
        self.logger.info(f"Current position: {pos} deg, status={status}")
        return pos, status



    # =========================
    # helium level
    # =========================
    def get_level(self):
        """
        He level を取得。
        これはあなたの環境で client.get_level() が実装済みである前提。
        """
        self._require_client()

        if not hasattr(self.client, "get_level"):
            msg = "This MultiPyVu Client does not have get_level(). Please add your custom wrapper first."
            self.logger.error(msg)
            raise AttributeError(msg)

        level, _ = self.client.get_level()
        self.logger.info(f"He level: {level} %")
        return level




@staticmethod
def Make_Sequence(
    Hi: List[float],
    dHi: List[float],
    kind: str = "Field",
    loop: bool = True,
) -> List[float]:

    logger = logging.getLogger(__name__)

    # =========================
    # validation
    # =========================
    if len(Hi) < 1:
        raise ValueError("Hi は少なくとも1点必要です。")

    if len(dHi) != max(len(Hi) - 1, 0):
        raise ValueError("len(dHi) は len(Hi)-1 である必要があります。")

    if any(step <= 0 for step in dHi):
        raise ValueError("dHi の各要素は正の値である必要があります。")

    kind_norm = str(kind).strip().lower()
    if kind_norm not in ("field", "temperature"):
        raise ValueError("kind は 'Field' または 'Temperature' でなければなりません。")

    # =========================
    # limit
    # =========================
    if kind_norm == "field":
        vmax_limit = 90000.0   # Oe
        vmin_limit = -90000.0
    else:
        vmax_limit = 400.0     # K
        vmin_limit = 4.2

    # =========================
    # 1点だけの場合
    # =========================
    if len(Hi) == 1:
        sequence = [float(Hi[0])]

        vmax = max(sequence)
        vmin = min(sequence)

        if vmax > vmax_limit or vmin < vmin_limit:
            raise ValueError(
                f"{kind} シーケンスが制限を超えました "
                f"(最大={vmax}, 最小={vmin}). "
                f"範囲は {vmin_limit} から {vmax_limit} までです。"
            )

        if kind_norm == "temperature" and loop:
            logger.warning("loop=True は Temperature では無視されます。")

        logger.info(f"{kind} Sequence: {sequence}")
        logger.info(f"測定点数: {len(sequence)}")
        return sequence

    # =========================
    # base sequence
    # =========================
    base: List[float] = []

    for i in range(len(dHi)):
        start = float(Hi[i])
        stop = float(Hi[i + 1])
        step = float(dHi[i])

        if start < stop:
            vals = list(np.arange(start, stop, step, dtype=float))
        elif start > stop:
            vals = list(np.arange(start, stop, -step, dtype=float))
        else:
            vals = [start]

        base.extend(vals)

    # 最終点追加
    base.append(float(Hi[-1]))

    # =========================
    # 重複削除
    # =========================
    cleaned: List[float] = []
    for v in base:
        if not cleaned or v != cleaned[-1]:
            cleaned.append(float(v))

    # =========================
    # loop（Fieldのみ）
    # =========================
    if kind_norm == "field" and loop:
        mirrored = [-v for v in cleaned]
        back = list(reversed(cleaned))
        sequence = cleaned + mirrored + back
    else:
        if kind_norm == "temperature" and loop:
            logger.warning("loop=True は Temperature では無視されます。")
        sequence = cleaned

    # =========================
    # limit check
    # =========================
    vmax = max(sequence)
    vmin = min(sequence)

    if vmax > vmax_limit or vmin < vmin_limit:
        raise ValueError(
            f"{kind} シーケンスが制限を超えました "
            f"(最大={vmax}, 最小={vmin}). "
            f"範囲は {vmin_limit} から {vmax_limit} までです。"
        )

    # =========================
    # log
    # =========================
    logger.info(f"{kind} Sequence: {sequence}")
    logger.info(f"測定点数: {len(sequence)}")

    return sequence


# In[ ]:


# from PPMS import PPMS
# import logging

# logger = logging.getLogger("PPMS")
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())

# with PPMS(logger=logger) as ppms:
#     current_field = ppms.set_field(
#         0.0,
#         rate_oe_per_sec=100.0,
#         approach_mode="linear",
#         field_mode="persistent",
#         wait=True,
#     )
#     print(current_field)

#     temperature = ppms.set_temperature(
#         300.0,
#         rate_k_per_min=10.0,
#         wait=True,
#     )
#     print(temperature)

#     pos = ppms.set_position(90.0, wait=True)
#     print(pos)

#     level = ppms.get_level()
#     print(level)

