#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import logging
from IPython.display import clear_output
from datetime import datetime
import os
from tkinter import filedialog
import matplotlib.pyplot as plt
import pandas as pd
import re
from matplotlib.figure import Figure

import tkinter as tk
root=tk.Tk()
root.attributes('-topmost', True)    # ファイル選択ウィンドウを最前面
root.withdraw()  


# プロットのデフォルトスタイル設定（クラス外で一度だけでOK）
plt.rcParams.update({
    "font.family": "Times New Roman",
    "xtick.direction": "in",
    "ytick.direction": "in",
    "xtick.top": True,
    "xtick.bottom": True,
    "ytick.left": True,
    "ytick.right": True,
    "xtick.minor.visible": True,
    "ytick.minor.visible": True,
    "xtick.major.width": 1.5,
    "ytick.major.width": 1.5,
    "xtick.minor.width": 1.0,
    "ytick.minor.width": 1.0,
    "xtick.major.size": 10,
    "ytick.major.size": 10,
    "xtick.minor.size": 5,
    "ytick.minor.size": 5,
    "figure.subplot.left": 0.07,
    "figure.subplot.bottom": 0.15,
    "figure.subplot.right": 0.97,
    "figure.subplot.top": 0.90,
    "font.size": 14,
    "axes.linewidth": 1.5,
    "legend.loc": "best",
    "axes.grid": True,
    "grid.color": "silver",
    "grid.linewidth": 1,
    "figure.dpi": 100
})

class FileOperation:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.propagate = False
        self.logger.debug("FileOperation インスタンスが作成されました。")

    @staticmethod
    def Read_parameter(skip: int = 0):
        # ファイル指定
        filetype = [("csvファイル","*.csv"), ("txtファイル","*.txt"), ("datファイル","*.dat"), ("すべて","*")]
        file_path = tk.filedialog.askopenfilename(filetypes = filetype, parent=root)
        if not file_path:
            return None  # キャンセルした場合は None
        try:
            df = pd.read_csv(file_path, skiprows=skip)
            return df
        except Exception as e:
            print(f"読み込み失敗: {e}")
            return None


    # @staticmethod
    # def SaveFile(data, Filename, mode="w"):
    #     try:
    #         data.to_csv(Filename, index=False, mode=mode)
    #         logging.getLogger("FileOperation").info(f"ファイル保存: {Filename}")
    #     except Exception as e:
    #         logging.getLogger("FileOperation").exception(f"保存エラー: {e}")
    @staticmethod
    def SaveFile(data, Filename, mode="w", PPMS_dat=False):
        import logging

        try:
            if PPMS_dat and mode == "w":
                # ヘッダーを書き込む
                with open(Filename, "w", encoding="utf-8") as f:
                    f.write("[Header]\n \n[Data]\n")
                
                # データは追記で書く
                data.to_csv(Filename, index=False, mode="a")
            else:
                # 通常保存
                data.to_csv(Filename, index=False, mode=mode)

            logging.getLogger("FileOperation").info(f"ファイル保存: {Filename}")

        except Exception as e:
            logging.getLogger("FileOperation").exception(f"保存エラー: {e}")

    @staticmethod
    def generate_filelist(dir_path, filelist, YMD, extension):
        return [os.path.join(dir_path, name + "_" + YMD + extension) for name in filelist]

    # def Make_file(self, PPMS_dat=False):
    #     fTyp = [("csv files", "*.csv"), ("data files", "*.dat"),
    #             ("Text files", "*.txt"), ("All files", "*.*")]
    #     dir_path = filedialog.asksaveasfilename(defaultextension=".dat", filetypes=fTyp)
    #     YMD = datetime.today().strftime("%Y%m%d_%H%M%S")
    #     Name = os.path.splitext(dir_path)[0] + "_"
    #     Filename = Name + YMD + ".csv"
    #     Figname  = Name + YMD + ".png"
    #     Information = Name + YMD + "_info.csv"
    #     logs_dir_name = os.path.join(os.path.dirname(Name), "logs")
    #     os.makedirs(logs_dir_name, exist_ok=True)
    #     Logname = os.path.join(logs_dir_name, os.path.basename(Name + YMD) + "_log.txt")
    #     return [Filename, Information, Figname, Logname]

    def Make_file(self, PPMS_dat=False):
        fTyp = [("csv files", "*.csv"), ("data files", "*.dat"),
                ("Text files", "*.txt"), ("All files", "*.*")]

        # デフォルト拡張子を切り替え
        default_ext = ".dat" if PPMS_dat else ".csv"
        data_ext = ".dat" if PPMS_dat else ".csv"

        dir_path = filedialog.asksaveasfilename(defaultextension=default_ext, filetypes=fTyp)
        YMD = datetime.today().strftime("%Y%m%d_%H%M%S")
        Name = os.path.splitext(dir_path)[0] + "_"
        Filename    = Name + YMD + data_ext
        Figname     = Name + YMD + ".png"
        Information = Name + YMD + "_info.csv"
        logs_dir_name = os.path.join(os.path.dirname(Name), "logs")
        os.makedirs(logs_dir_name, exist_ok=True)
        Logname = os.path.join(logs_dir_name, os.path.basename(Name + YMD) + "_log.txt")

        return [Filename, Information, Figname, Logname]

    @staticmethod
    def add_temp_to_filenames(Filename, Infoname, Figname, Temp):
        """
        Make_file()で作成したファイル名に温度（XXXK）を付加する
        Lognameは無視する版
        """

        import os

        temp = int(round(float(Temp)))  # 念のためfloat対応＋丸め
        temp_suffix = f"_{temp}K"

        def _add_suffix(path):
            base, ext = os.path.splitext(path)
            return f"{base}{temp_suffix}{ext}"

        Filename_T = _add_suffix(Filename)
        Infoname_T = _add_suffix(Infoname)
        Figname_T  = _add_suffix(Figname)

        return Filename_T, Infoname_T, Figname_T
    
    
    def Make_file_dict(self, dictional, shift):
        dir_path = filedialog.askdirectory()
        YMD = datetime.today().strftime("%Y%m%d_%H%M%S")
        Angle = [str(value[0] + shift).zfill(3) for value in dictional.values()]
        unit = [value[1] for value in dictional.values()]
        TF_list = [value[2] for value in dictional.values()]
        Angle_unit = [a + u for a, u in zip(Angle, unit)]
        Filelist = self.generate_filelist(dir_path, Angle_unit, YMD, ".csv")
        Figlist  = self.generate_filelist(dir_path, Angle_unit, YMD, ".png")
        Infolist = self.generate_filelist(dir_path, Angle_unit, YMD, "_info.csv")
        logs_dir_name = os.path.join(dir_path, "logs")
        os.makedirs(logs_dir_name, exist_ok=True)
        Logname = os.path.join(logs_dir_name, YMD + "_log.txt")
        return [Filelist, Infolist, Figlist, Logname, TF_list]

    # @staticmethod
    # def plot_figure(Data, Harmonics):
    #     logger = logging.getLogger("FileOperation")
    #     logger.info("プロットを開始します。")
    #     logger.debug(f"Harmonics: {Harmonics}")
    #     logger.debug(f"Data columns: {Data.columns.tolist()}")

    #     N = len(Harmonics)
    #     fig, axs = plt.subplots(2, N, figsize=(5 * N, 10))

    #     for Harm_Num in range(N):
    #         idx = Harmonics[Harm_Num]
    #         label = Data.columns[0]

    #         if N == 1:
    #             axs[0].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_X_mean"], yerr=Data[f"Harm{idx}_X_std"], marker='o')
    #             axs[0].set_title(f'{idx}-Harmonic X')
    #             axs[0].set_xlabel(label)
    #             axs[0].set_ylabel(f"Harm{idx}_X_mean")

    #             axs[1].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_Y_mean"], yerr=Data[f"Harm{idx}_Y_std"], marker='o')
    #             axs[1].set_title(f'{idx}-Harmonic Y')
    #             axs[1].set_xlabel(label)
    #             axs[1].set_ylabel(f"Harm{idx}_Y_mean")
    #         else:
    #             axs[0, Harm_Num].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_X_mean"], yerr=Data[f"Harm{idx}_X_std"], marker='o')
    #             axs[0, Harm_Num].set_title(f'{idx}-Harmonic X')
    #             axs[0, Harm_Num].set_xlabel(label)
    #             axs[0, Harm_Num].set_ylabel(f"Harm{idx}_X_mean")

    #             axs[1, Harm_Num].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_Y_mean"], yerr=Data[f"Harm{idx}_Y_std"], marker='o')
    #             axs[1, Harm_Num].set_title(f'{idx}-Harmonic Y')
    #             axs[1, Harm_Num].set_xlabel(label)
    #             axs[1, Harm_Num].set_ylabel(f"Harm{idx}_Y_mean")

    #     plt.tight_layout()
    #     plt.show()
    #     logger.info("プロットが正常に完了しました。")
    #     return fig

    @staticmethod
    def plot_figure(
        Data: pd.DataFrame,
        Harmonics: list[int],
        *,
        x_col: str | None = None,        # 既定: Dataの先頭列をXに
        title_prefix: str = "",          # タイトルの先頭に付けたい文字があれば
        savepath: str | None = None,     # 画像保存パス（指定時のみ保存）
        axs=None,                        # 既存Axes配列(2 x N)を渡せる
        show: bool = True,               # 既定True（Notebook時にそのまま表示）
        dpi: int = 120,
    ):
        """
        複数高調波（X/Y）を 2 x N で並べて描画。
        - x_col 未指定なら Data の先頭列をXとみなす
        - 各 Harm{n}_X/Y に対して、_std列があればerrorbar、無ければline+marker
        - axs が渡された場合はそこへ描画（通常 show=False 扱い）
        - axs が無い場合は新規 Figure/Axes を生成。show=Trueなら plt.show()
        - savepath があれば保存
        戻り値: (fig, axs)
        """
        # import logging
        # import matplotlib
        # from matplotlib.figure import Figure
        # import matplotlib.pyplot as plt

        logger = logging.getLogger("FileOperation")
        logger.info("プロットを開始します。")
        logger.debug(f"Harmonics: {Harmonics}")
        logger.debug(f"Data columns: {Data.columns.tolist()}")

        # --- X列の決定 ---
        if x_col is None:
            if len(Data.columns) == 0:
                raise ValueError("Data に列がありません。")
            x_col = Data.columns[0]
        if x_col not in Data.columns:
            raise KeyError(f"x_col='{x_col}' が Data にありません。columns={list(Data.columns)}")

        x = Data[x_col]
        N = len(Harmonics)

        # --- Figure/Axes 準備 ---
        created_new_fig = False
        if axs is None:
            fig, axs = plt.subplots(2, N, figsize=(5 * max(N, 1), 10), dpi=dpi)
            created_new_fig = True
            # N=1のときでも2次元扱いに統一
            if N == 1:
                axs = (axs[0], axs[1])  # tuple of Axes
        else:
            # 既存のAxesに描画（fig取得）
            if N == 1:
                # axs は (ax_top, ax_bottom) または np.ndarray(2,) を想定
                fig = axs[0].figure
                axs[0].clear(); axs[1].clear()
            else:
                # axs は np.ndarray shape=(2, N) を想定
                fig = axs[0, 0].figure
                for r in range(2):
                    for c in range(N):
                        axs[r, c].clear()

        # --- 描画ループ ---
        for j, h in enumerate(Harmonics):
            col_X_mean  = f"Harm{h}_X_mean"
            col_X_std   = f"Harm{h}_X_std"
            col_Y_mean  = f"Harm{h}_Y_mean"
            col_Y_std   = f"Harm{h}_Y_std"

            # 軸の取得（N=1 だけ添え字形が異なる）
            if N == 1:
                axX, axY = axs[0], axs[1]
            else:
                axX, axY = axs[0, j], axs[1, j]

            # ---- X成分 ----
            if col_X_mean not in Data.columns:
                logger.warning(f"{col_X_mean} が見つかりません。スキップします。")
            else:
                y = Data[col_X_mean]
                if col_X_std in Data.columns:
                    axX.errorbar(x, y, yerr=Data[col_X_std], marker="o", linestyle="-")
                else:
                    axX.plot(x, y, marker="o", linestyle="-")
                ttl = f"{title_prefix}{h}-Harmonic X" if title_prefix else f"{h}-Harmonic X"
                axX.set_title(ttl)
                axX.set_xlabel(str(x_col))
                axX.set_ylabel(col_X_mean)
                axX.grid(True, alpha=0.3)

            # ---- Y成分 ----
            if col_Y_mean not in Data.columns:
                logger.warning(f"{col_Y_mean} が見つかりません。スキップします。")
            else:
                y = Data[col_Y_mean]
                if col_Y_std in Data.columns:
                    axY.errorbar(x, y, yerr=Data[col_Y_std], marker="o", linestyle="-")
                else:
                    axY.plot(x, y, marker="o", linestyle="-")
                ttl = f"{title_prefix}{h}-Harmonic Y" if title_prefix else f"{h}-Harmonic Y"
                axY.set_title(ttl)
                axY.set_xlabel(str(x_col))
                axY.set_ylabel(col_Y_mean)
                axY.grid(True, alpha=0.3)

        fig.tight_layout()

        # --- 保存 ---
        if savepath:
            fig.savefig(savepath, dpi=dpi, bbox_inches="tight")

        # --- 表示制御 ---
        if created_new_fig and show:
            plt.show()

        logger.info("プロットが正常に完了しました。")
        return fig, axs


    @staticmethod
    def plot_XY(
        Data: pd.DataFrame,
        X_col: str = "elapse_time",
        Y_col: str = "Voltage_ch1_mean",
        std_col: str | None = "Voltage_ch1_std",
        title: str = "Voltage vs Time (CH1)",
        xlabel: str = "Elapsed time [s]",
        ylabel: str = "Voltage [V]",
        savepath: str | None = None,
        ax=None,                # 既存Axes（埋め込み時などに使用）
        show: bool = True,      # ← 追加：既定は True（スクリプト用途で従来どおり表示）
    ):
        """
        汎用プロット:
        - std_col があれば errorbar、なければ line+marker
        - ax を渡された場合はその Axes に描画（原則 show しない）
        - ax が無い場合は新規 Figure を作成。show=True なら plt.show() で表示
        """

        # 入力チェック
        for col in (X_col, Y_col):
            if col not in Data.columns:
                raise KeyError(f"'{col}' not found in Data. columns={list(Data.columns)}")
        if std_col and std_col not in Data.columns:
            raise KeyError(f"'{std_col}' not found in Data. columns={list(Data.columns)}")

        # Axes 準備
        created_new_fig = False
        if ax is None:
            fig = Figure(figsize=(8, 5), dpi=100)
            ax = fig.add_subplot(111)
            created_new_fig = True
        else:
            fig = ax.figure
            ax.clear()

        # 描画
        if std_col is None:
            ax.plot(Data[X_col], Data[Y_col], marker="o", linestyle="-")
        else:
            ax.errorbar(Data[X_col], Data[Y_col], yerr=Data[std_col], marker="o", linestyle="-")

        # 体裁
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        # 保存
        if savepath:
            fig.savefig(savepath, dpi=200, bbox_inches="tight")

        # 表示制御
        # - 新規 Figure を作った時だけ show の判定を行う（ax を渡された時は表示しない）
        if created_new_fig and show:
            # pyplot は必要時だけ import（起動を軽量に）
            import matplotlib.pyplot as plt
            plt.show()

        return fig





class PlotResults:

    def Read_file(skip = 0):
        # ファイル指定
        idir = 'C:\\Users\HIROKI\Desktop'      # 初期ディレクトリ
        filetype = [("text, csvファイル","*.txt; *.csv"), ("datファイル","*.dat"), ("すべて","*")]
        file_path = tk.filedialog.askopenfilename(filetypes = filetype, parent=root, initialdir = idir)
        info_path = os.path.splitext(file_path)[0] + "_info.csv"
        Raw_Data  = pd.read_csv(file_path, header=skip)
        info_Data = pd.read_csv(info_path, header=skip)
        Figname    = os.path.splitext(file_path)[0] + ".png"
        return Raw_Data, info_Data, Figname

    def plot_figure(Data):

        Harmonics = []
        filtered_Data = Data.loc[:, Data.columns.str.contains("X_mean", case=False, regex=False)]
        N = len(filtered_Data.columns)

        for col in filtered_Data.columns:
            nums = re.findall(r'\d+', col)  # カラム名中の数字部分をすべて抽出（リストで返る）
            Harmonics.extend(nums)

        fig, axs = plt.subplots(2, N, figsize=(5 * N, 10))

        for Harm_Num in range(N):
            idx = Harmonics[Harm_Num]
            label = Data.columns[0]

            if N == 1:
                axs[0].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_X_mean"], yerr=Data[f"Harm{idx}_X_std"], marker='o')
                axs[0].set_title(f'{idx}-Harmonic X')
                axs[0].set_xlabel(label)
                axs[0].set_ylabel(f"Harm{idx}_X_mean")

                axs[1].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_Y_mean"], yerr=Data[f"Harm{idx}_Y_std"], marker='o')
                axs[1].set_title(f'{idx}-Harmonic Y')
                axs[1].set_xlabel(label)
                axs[1].set_ylabel(f"Harm{idx}_Y_mean")
            else:
                axs[0, Harm_Num].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_X_mean"], yerr=Data[f"Harm{idx}_X_std"], marker='o')
                axs[0, Harm_Num].set_title(f'{idx}-Harmonic X')
                axs[0, Harm_Num].set_xlabel(label)
                axs[0, Harm_Num].set_ylabel(f"Harm{idx}_X_mean")

                axs[1, Harm_Num].errorbar(Data.iloc[:, 0], Data[f"Harm{idx}_Y_mean"], yerr=Data[f"Harm{idx}_Y_std"], marker='o')
                axs[1, Harm_Num].set_title(f'{idx}-Harmonic Y')
                axs[1, Harm_Num].set_xlabel(label)
                axs[1, Harm_Num].set_ylabel(f"Harm{idx}_Y_mean")

        plt.tight_layout()
        plt.show()
        return fig


# In[ ]:


def setup_logger(log_file=None, logger_name="Logger", level=logging.DEBUG):
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



