"""
Chanlun-Pro cl.py 替代实现
使用 Vespa314/chan.py 的开源缠论计算引擎替代原始的 PyArmor 加密版本。

本文件实现 ICL 接口（定义见 cl_interface.py），内部委托给 chan.py 的 CChan。
"""
import datetime
import logging
import math
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from chanlun.cl_interface import (
    BC, BI, CLKline, FX, ICL, Kline, LINE, MMD, TZXL, XLFX, XD, ZS,
    Config as CLConfig,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ──────────────────────────────────────────────
# 依赖 chan.py
# ──────────────────────────────────────────────
try:
    from Chan import CChan as ChanCChan
    from ChanConfig import CChanConfig
    from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE, DATA_FIELD, FX_TYPE as ChanFXType, BI_DIR
    from Common.CTime import CTime
    from KLine.KLine_Unit import CKLine_Unit
except ImportError as e:
    logger.warning(f"chan.py 未安装: {e}")
    raise


# ── 频率映射 ──
_FREQ_MAP = {
    "1m":  KL_TYPE.K_1M, "5m":  KL_TYPE.K_5M, "15m": KL_TYPE.K_15M,
    "30m": KL_TYPE.K_30M, "60m": KL_TYPE.K_60M,
    "d":   KL_TYPE.K_DAY, "w":  KL_TYPE.K_WEEK,
    "m":   KL_TYPE.K_MON, "month": KL_TYPE.K_MON,
}


def _parse_freq(frequency: str) -> KL_TYPE:
    freq = frequency.lower()
    if freq in _FREQ_MAP:
        return _FREQ_MAP[freq]
    if freq.endswith("m"):
        try:
            m = int(freq[:-1])
            if m <= 1:   return KL_TYPE.K_1M
            if m <= 3:   return KL_TYPE.K_3M
            if m <= 5:   return KL_TYPE.K_5M
            if m <= 15:  return KL_TYPE.K_15M
            if m <= 30:  return KL_TYPE.K_30M
            return KL_TYPE.K_60M
        except ValueError:
            pass
    return KL_TYPE.K_DAY


def _make_ctime(dt_val) -> CTime:
    """将各种日期格式转为 CTime"""
    if isinstance(dt_val, datetime.datetime):
        return CTime(dt_val.year, dt_val.month, dt_val.day,
                     dt_val.hour, dt_val.minute, auto=False)
    if isinstance(dt_val, pd.Timestamp):
        dt_val = dt_val.to_pydatetime()
        return CTime(dt_val.year, dt_val.month, dt_val.day,
                     dt_val.hour, dt_val.minute, auto=False)
    if isinstance(dt_val, str):
        parts = dt_val.replace('T', ' ').replace('-', ' ').replace(':', ' ').split()
        return CTime(int(parts[0]), int(parts[1]), int(parts[2]),
                     int(parts[3]) if len(parts) > 3 else 0,
                     int(parts[4]) if len(parts) > 4 else 0, auto=False)
    return CTime(2000, 1, 1, 0, 0, auto=False)


def _macd_manual(prices: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """手工 EMA 计算 MACD"""
    def ema(data, period):
        result = np.zeros_like(data)
        multiplier = 2.0 / (period + 1)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
        return result
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    dif = ema12 - ema26
    dea = ema(dif, 9)
    hist = 2 * (dif - dea)
    return dif, dea, hist


# ═══════════════════════════════════════════════
#  CL — 实现 ICL 接口
# ═══════════════════════════════════════════════

class CL(ICL):
    """缠论计算核心适配器。底层使用 chan.py 的 CChan。"""

    def __init__(
        self,
        code: str,
        frequency: str,
        config: Union[dict, None] = None,
        start_datetime: datetime.datetime = None,
    ):
        self._code = code
        self._frequency_str = frequency
        self._kl_type = _parse_freq(frequency)
        self._cl_config = config or {}

        # 原始 K 线缓存 (chanlun-pro 格式)
        self._src_klines: List[Kline] = []
        self._cl_klines: List[CLKline] = []
        self._idx: dict = {}

        # 结果缓存 (chanlun-pro 格式)
        self._cached_fxs: List[FX] = []
        self._cached_bis: List[BI] = []
        self._cached_xds: List[XD] = []
        self._cached_bi_zss: List[ZS] = []
        self._cached_bi_zss_by_type: Dict[str, List[ZS]] = {}

        # chan.py 实例
        self._cchan: Optional[ChanCChan] = None
        self._processed = False

    # ─── ICL 公共方法 ──────────────────────────

    def process_klines(self, klines: pd.DataFrame):
        """计算 K 线缠论数据（可增量调用）"""
        if klines is None or len(klines) == 0:
            return self

        df = klines.copy()
        # 统一日期列名
        if 'date' not in df.columns and 'datetime' in df.columns:
            df = df.rename(columns={'datetime': 'date'})
        if 'date' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'])
        if 'date' not in df.columns and 'timestamp' in df.columns:
            df['date'] = pd.to_datetime(df['timestamp'], unit='s')

        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                raise ValueError(f"DataFrame 缺少列: {col}")

        # 1. 保存原始 K 线
        self._src_klines = []
        for i, row in df.iterrows():
            dt = row['date']
            if isinstance(dt, pd.Timestamp):
                dt = dt.to_pydatetime()
            elif isinstance(dt, str):
                dt = datetime.datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S")
            self._src_klines.append(Kline(
                index=i, date=dt,
                h=float(row['high']), l=float(row['low']),
                o=float(row['open']), c=float(row['close']),
                a=float(row.get('amount', row['volume'])),
            ))

        # 2. 构建 CKLine_Unit 列表
        klu_list: List[CKLine_Unit] = []
        for i, row in df.iterrows():
            ct = _make_ctime(row['date'])
            klu = CKLine_Unit({
                'time_key': ct,
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            }, autofix=True)
            klu.kl_type = self._kl_type
            klu_list.append(klu)

        # 3. 调用 chan.py
        try:
            self._invoke_cchan(klu_list)
        except Exception as e:
            logger.error(f"CChan trigger_load 失败: {e}", exc_info=True)

        # 4. 更新指标
        self._update_idx()

        # 5. 转换结果
        self._convert_results()
        self._processed = True
        return self

    def _build_chan_config(self) -> dict:
        """将 chanlun-pro 的配置映射到 chan.py 的 CChanConfig 参数"""
        cfg = {}
        cl_cfg = self._cl_config or {}

        # 基础配置
        cfg['trigger_step'] = True
        cfg['skip_step'] = 0
        cfg['print_warning'] = False
        cfg['print_err_time'] = False
        cfg['kl_data_check'] = False
        cfg['auto_skip_illegal_sub_lv'] = True

        # ── 分型包含关系 fx_bh 映射 ──
        fx_bh = cl_cfg.get('fx_bh', None)
        if fx_bh == 'no':  # FX_BH_NO: 顶不在底中，底不在顶中
            cfg['bi_fx_check'] = 'strict'
        elif fx_bh == 'dingdi':  # FX_BH_DINGDI: 顶可以在底中，但底不可以在顶中
            cfg['bi_fx_check'] = 'loss'
        elif fx_bh == 'diding':  # FX_BH_DIDING: 底可以在顶中，但顶不可以在底中
            cfg['bi_fx_check'] = 'half'
        else:
            cfg['bi_fx_check'] = 'strict'

        # ── 允许严格分型 ──
        allow_strict = cl_cfg.get('allow_bi_fx_strict', None)
        if allow_strict is not None:
            cfg['bi_strict'] = bool(allow_strict)
        else:
            cfg['bi_strict'] = True

        # ── 笔类型映射 ──
        bi_type = cl_cfg.get('bi_type', None)
        if bi_type == 'jdb':  # 简单笔
            cfg['bi_algo'] = 'normal'
        elif bi_type == 'dd':  # 顶底成笔
            cfg['bi_algo'] = 'diyi'
        # old/new 都是 normal，区别在 bi_fx_check 上

        # ── 笔内分型次高低 ──
        bi_fx_cgd = cl_cfg.get('bi_fx_cgd', None)
        if bi_fx_cgd is not None:
            cfg['bi_allow_sub_peak'] = bool(bi_fx_cgd)
        else:
            cfg['bi_allow_sub_peak'] = True

        # ── 分型检查K线数量 ──
        fx_check_k = cl_cfg.get('fx_check_k_nums', None)
        if fx_check_k is not None:
            # chan.py 不支持
            pass

        # ── 中枢 ──
        zs_type = cl_cfg.get('zs_bi_type', None)
        if zs_type == 'dn':  # 段内中枢
            cfg['zs_algo'] = 'normal'
        else:
            cfg['zs_algo'] = 'normal'

        zs_combine = cl_cfg.get('zs_optimize', None)
        if zs_combine is not None:
            cfg['zs_combine'] = bool(zs_combine)
        else:
            cfg['zs_combine'] = True

        return cfg

    def _invoke_cchan(self, klu_list: List[CKLine_Unit]):
        """创建/复用 CChan 并喂入数据"""
        if self._cchan is None:
            chan_cfg = self._build_chan_config()
            ch_config = CChanConfig(chan_cfg)
            self._cchan = ChanCChan(
                code=self._code, data_src=DATA_SRC.BAO_STOCK,
                lv_list=[self._kl_type], config=ch_config, autype=AUTYPE.QFQ,
            )
        self._cchan.trigger_load({self._kl_type: klu_list})

    def _update_idx(self):
        """更新 MACD 指标缓存"""
        if not self._src_klines:
            return
        closes = np.array([k.c for k in self._src_klines])
        try:
            import talib
            macd_line, signal, hist = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
        except ImportError:
            macd_line, signal, hist = _macd_manual(closes)
        self._idx = {
            "macd": {
                "dea": signal.tolist() if hasattr(signal, 'tolist') else list(signal),
                "dif": macd_line.tolist() if hasattr(macd_line, 'tolist') else list(macd_line),
                "hist": hist.tolist() if hasattr(hist, 'tolist') else list(hist),
            }
        }

    def _convert_results(self):
        """将 chan.py 结果转换为 chanlun-pro 类型"""
        if self._cchan is None:
            return

        kl_list = self._cchan[0]

        # ── 分型 ──
        self._cached_fxs = []
        for klc in kl_list:
            try:
                if klc.fx is not None and str(klc.fx) not in ("UNKNOWN", "unknown"):
                    fx_type = "ding" if str(klc.fx) == "TOP" else "di" if str(klc.fx) == "BOTTOM" else None
                    if fx_type is None:
                        continue
                    ms_klines = list(klc.lst)[:3]
                    mid_klu = klc.lst[1] if len(klc.lst) > 1 else klc.lst[0]
                    val = klc.high if fx_type == "ding" else klc.low

                    clk = CLKline(
                        k_index=mid_klu.idx if hasattr(mid_klu, 'idx') else 0,
                        date=mid_klu.time if hasattr(mid_klu, 'time') else datetime.datetime.now(),
                        h=klc.high, l=klc.low, o=klc.low, c=klc.high, a=0,
                        klines=[
                            Kline(idx, k.time, k.high, k.low, k.open, k.close, 0)
                            for idx, k in enumerate(ms_klines)
                        ] if ms_klines else [],
                    )
                    self._cached_fxs.append(FX(
                        _type=fx_type, k=clk, klines=[clk],
                        val=val, index=mid_klu.idx if hasattr(mid_klu, 'idx') else 0,
                        done=True,
                    ))
            except Exception:
                pass

        # ── 笔 ──
        self._cached_bis = []
        for bi in kl_list.bi_list:
            try:
                bi_type = "up" if bi.dir == BI_DIR.UP else "down"
                start_fx = self._find_or_create_fx(bi.begin_klc, "bottom" if bi_type == "up" else "top")
                end_fx = self._find_or_create_fx(bi.end_klc, "top" if bi_type == "up" else "bottom")

                cl_bi = BI(start=start_fx, end=end_fx, _type=bi_type, index=bi.idx if hasattr(bi, 'idx') else 0)
                cl_bi.high = max(bi.begin_klc.high, bi.end_klc.high)
                cl_bi.low = min(bi.begin_klc.low, bi.end_klc.low)
                cl_bi.zs_high = cl_bi.high
                cl_bi.zs_low = cl_bi.low

                # 保存时间戳（用于前端画图定位）
                try:
                    if hasattr(bi, 'begin_klc') and len(bi.begin_klc.lst) > 0:
                        cl_bi._start_time = str(bi.begin_klc.lst[0].time)
                    if hasattr(bi, 'end_klc') and len(bi.end_klc.lst) > 0:
                        cl_bi._end_time = str(bi.end_klc.lst[-1].time)
                except Exception:
                    pass

                self._cached_bis.append(cl_bi)
            except Exception:
                pass

        # ── 线段 ──
        self._cached_xds = []
        for seg in kl_list.seg_list:
            try:
                xd_type = "up" if seg.dir == "up" or (hasattr(seg, 'is_up') and seg.is_up()) else "down"
                start_fx = FX(
                    _type="di" if xd_type == "up" else "ding",
                    k=self._make_dummy_clk(), klines=[], val=0,
                )
                end_fx = FX(
                    _type="ding" if xd_type == "up" else "di",
                    k=self._make_dummy_clk(), klines=[], val=0,
                )
                cl_xd = XD(start=start_fx, end=end_fx, start_line=None, end_line=None,
                           _type=xd_type, index=seg.idx if hasattr(seg, 'idx') else 0)
                # 从包含的笔计算高/低点
                _bi_lst = getattr(seg, 'bi_list', [])
                _hs = [max(bi.begin_klc.high, bi.end_klc.high) for bi in _bi_lst if hasattr(bi, 'begin_klc') and hasattr(bi, 'end_klc')]
                _ls = [min(bi.begin_klc.low, bi.end_klc.low) for bi in _bi_lst if hasattr(bi, 'begin_klc') and hasattr(bi, 'end_klc')]
                cl_xd.high = max(_hs) if _hs else 0
                cl_xd.low = min(_ls) if _ls else 0
                # 保存时间戳
                try:
                    if hasattr(seg, 'start_bi') and hasattr(seg.start_bi, 'begin_klc') and len(seg.start_bi.begin_klc.lst) > 0:
                        cl_xd._start_time = str(seg.start_bi.begin_klc.lst[0].time)
                    if hasattr(seg, 'end_bi') and hasattr(seg.end_bi, 'end_klc') and len(seg.end_bi.end_klc.lst) > 0:
                        cl_xd._end_time = str(seg.end_bi.end_klc.lst[-1].time)
                except Exception:
                    pass
                self._cached_xds.append(cl_xd)
            except Exception:
                pass

        # ── 笔中枢 ──
        self._cached_bi_zss = []
        self._cached_bi_zss_by_type = {"bz": []}
        for zs in kl_list.zs_list:
            try:
                start_fx = FX(_type="unknown", k=self._make_dummy_clk(), klines=[], val=0)
                end_fx = FX(_type="unknown", k=self._make_dummy_clk(), klines=[], val=0)
                cl_zs = ZS(
                    zs_type="bi", start=start_fx, end=end_fx,
                    zg=zs.high if hasattr(zs, 'high') else 0,
                    zd=zs.low if hasattr(zs, 'low') else 0,
                    gg=zs.peak_high if hasattr(zs, 'peak_high') else 0,
                    dd=zs.peak_low if hasattr(zs, 'peak_low') else 0,
                    _type="up", index=len(self._cached_bi_zss),
                )
                self._cached_bi_zss.append(cl_zs)
                self._cached_bi_zss_by_type.setdefault("bz", []).append(cl_zs)
            except Exception:
                pass

    def _find_or_create_fx(self, klc, fx_hint: str) -> FX:
        """找匹配的分型或创建虚拟的"""
        for fx in self._cached_fxs:
            if hasattr(fx.k, 'date') and hasattr(klc.lst[0], 'time'):
                if str(fx.k.date)[:10] == str(klc.lst[0].time)[:10]:
                    return fx
        return FX(
            _type=fx_hint,
            k=self._make_dummy_clk(),
            klines=[],
            val=klc.high if "top" in fx_hint else klc.low,
        )

    def _make_dummy_clk(self) -> CLKline:
        return CLKline(
            k_index=0, date=datetime.datetime(2000, 1, 1),
            h=0, l=0, o=0, c=0, a=0,
        )

    # ─── ICL getter 方法 ───────────────────────

    def get_code(self) -> str:
        return self._code

    def get_frequency(self) -> str:
        return self._frequency_str

    def get_config(self) -> dict:
        return self._cl_config

    def get_src_klines(self) -> List[Kline]:
        return self._src_klines

    def get_klines(self) -> List[Kline]:
        return self._src_klines

    def get_cl_klines(self) -> List[CLKline]:
        return self._cl_klines

    def get_idx(self) -> dict:
        if not self._idx:
            self._update_idx()
        return self._idx

    def get_fxs(self) -> List[FX]:
        return self._cached_fxs

    def get_bis(self) -> List[BI]:
        return self._cached_bis

    def get_xds(self) -> List[XD]:
        return self._cached_xds

    def get_bi_zss(self, zs_type: str = None) -> List[ZS]:
        if zs_type is None:
            return self._cached_bi_zss
        return self._cached_bi_zss_by_type.get(zs_type, self._cached_bi_zss)

    def get_xd_zss(self, zs_type: str = None) -> List[ZS]:
        return []

    def get_zsd_zss(self) -> List[ZS]:
        return []

    def get_qsd_zss(self) -> List[ZS]:
        return []

    def get_zsds(self) -> List[XD]:
        return []

    def get_qsds(self) -> List[XD]:
        return []

    def get_last_bi_zs(self) -> Union[ZS, None]:
        return self._cached_bi_zss[-1] if self._cached_bi_zss else None

    def get_last_xd_zs(self) -> Union[ZS, None]:
        return None

    def create_dn_zs(self, zs_type: str, lines: List[LINE],
                     max_line_num: int = 999, zs_include_last_line=True) -> List[ZS]:
        if len(lines) < 3:
            return []
        highs = [l.high for l in lines if hasattr(l, 'high')]
        lows = [l.low for l in lines if hasattr(l, 'low')]
        if not highs or not lows:
            return []
        start_fx = FX(_type="unknown", k=self._make_dummy_clk(), klines=[], val=0)
        end_fx = FX(_type="unknown", k=self._make_dummy_clk(), klines=[], val=0)
        return [ZS(
            zs_type="bi", start=start_fx, end=end_fx,
            zg=min(highs), zd=max(lows),
            gg=max(highs), dd=min(lows),
            _type="up", index=0,
        )]

    def beichi_pz(self, zs: ZS, now_line: LINE) -> Tuple[bool, Union[LINE, None]]:
        return False, None

    def beichi_qs(self, lines: List[LINE], zss: List[ZS], now_line: LINE) -> Tuple[bool, List[LINE]]:
        return False, []

    def zss_is_qs(self, one_zs: ZS, two_zs: ZS) -> Tuple[str, None]:
        if one_zs.dd is not None and two_zs.zg is not None:
            if two_zs.zg > one_zs.zg and two_zs.zd > one_zs.zd:
                return "up"
            return "down" if two_zs.zg < one_zs.zg else None  # type: ignore
        return None, None
