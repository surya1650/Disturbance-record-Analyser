import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from comtrade import Comtrade
from scipy.fft import fft, fftfreq

# ==========================================
# Step 1: Configuration and Channel Mapping
# ==========================================
# Map common relay channel names to standard phase labels.
CHANNEL_MAP: Dict[str, List[str]] = {
    "Phase A": ["IA", "IL1", "I_A", "VA", "VL1", "V_A", "R", "IR"],
    "Phase B": ["IB", "IL2", "I_B", "VB", "VL2", "V_B", "Y", "IY"],
    "Phase C": ["IC", "IL3", "I_C", "VC", "VL3", "V_C", "B", "IB"],
    "Neutral": ["IN", "IE", "I_N", "VN", "VE", "V_N", "IG"],
}

ANALOG_PREFIX = "A_"
DIGITAL_PREFIX = "D_"


def standardize_channel_name(raw_name: str) -> str:
    """Match a raw COMTRADE channel name to a standardized phase label."""
    raw_upper = raw_name.upper()
    for normalized, aliases in CHANNEL_MAP.items():
        if any(alias in raw_upper for alias in aliases):
            return normalized
    return raw_name.strip()


def is_file_like(obj: Any) -> bool:
    return hasattr(obj, "read") and callable(getattr(obj, "read"))


def _normalize_label(raw_name: str) -> str:
    return raw_name.strip().replace(" ", "_").replace("/", "_").replace("__", "_")


# ==========================================
# Step 1: COMTRADE Parsing Logic
# ==========================================
class ComtradeParser:
    """Load COMTRADE CFG/DAT pairs and return a normalized pandas DataFrame."""

    def __init__(self) -> None:
        self.comtrade = Comtrade()
        self._temporary_paths: List[str] = []

    def _write_temp_file(self, upload: Any, suffix: str) -> str:
        if isinstance(upload, str) and os.path.exists(upload):
            return upload
        if not is_file_like(upload):
            raise ValueError("Upload must be a path or a file-like object.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(upload.read())
            self._temporary_paths.append(tmp_file.name)
            return tmp_file.name

    def _cleanup(self) -> None:
        for path in self._temporary_paths:
            try:
                os.remove(path)
            except OSError:
                pass
        self._temporary_paths.clear()

    def load_pair(self, cfg_file: Any, dat_file: Any) -> pd.DataFrame:
        cfg_path = self._write_temp_file(cfg_file, suffix=".cfg")
        dat_path = self._write_temp_file(dat_file, suffix=".dat")

        try:
            self.comtrade.load(cfg_path, dat_path)
            return self._build_dataframe()
        finally:
            self._cleanup()

    def _build_dataframe(self) -> pd.DataFrame:
        timestamps = np.array(self.comtrade.time, dtype=float)
        data: Dict[str, Any] = {"timestamp": timestamps}

        for idx, raw_name in enumerate(self.comtrade.analog_channel_ids):
            phase_name = standardize_channel_name(raw_name)
            label = _normalize_label(f"{ANALOG_PREFIX}{phase_name}_{raw_name}")
            data[label] = np.asarray(self.comtrade.analog[idx], dtype=float)

        for idx, raw_name in enumerate(self.comtrade.status_channel_ids):
            label = _normalize_label(f"{DIGITAL_PREFIX}{raw_name}")
            data[label] = np.asarray(self.comtrade.status[idx], dtype=int)

        df = pd.DataFrame(data)
        df["sampling_rate"] = self._estimate_sampling_rate(timestamps)
        return df

    @staticmethod
    def _estimate_sampling_rate(timestamps: np.ndarray) -> float:
        if len(timestamps) < 2:
            return 1000.0
        dt = np.diff(timestamps)
        median_dt = float(np.median(dt))
        return 1.0 / median_dt if median_dt > 0 else 1000.0


# ==========================================
# Step 4: Mathematical Analysis Functions
# ==========================================
class AnalysisTools:
    @staticmethod
    def true_rms(signal: pd.Series, network_freq: float, sampling_rate: float) -> pd.Series:
        window = max(int(round(sampling_rate / network_freq)), 1)
        squared = signal.astype(float).pow(2)
        return np.sqrt(squared.rolling(window=window, min_periods=1).mean())

    @staticmethod
    def fft_spectrum(time: np.ndarray, signal: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        if len(signal) < 4:
            return np.array([]), np.array([])
        dt = float(np.median(np.diff(time))) if len(time) > 1 else 1.0 / 1000.0
        windowed = signal - np.mean(signal)
        yf = fft(windowed)
        xf = fftfreq(len(windowed), dt)[: len(windowed) // 2]
        mags = 2.0 / len(windowed) * np.abs(yf[: len(windowed) // 2])
        return xf, mags

    @staticmethod
    def symmetrical_components(ia: pd.Series, ib: pd.Series, ic: pd.Series) -> Dict[str, pd.Series]:
        a = complex(-0.5, np.sqrt(3) / 2)
        a2 = complex(-0.5, -np.sqrt(3) / 2)

        ia_f = ia.astype(float)
        ib_f = ib.astype(float)
        ic_f = ic.astype(float)

        pos = (ia_f + a * ib_f + a2 * ic_f) / 3
        neg = (ia_f + a2 * ib_f + a * ic_f) / 3
        zero = (ia_f + ib_f + ic_f) / 3

        return {
            "positive": pos,
            "negative": neg,
            "zero": zero,
        }

    @staticmethod
    def impedance_trajectory(voltage: pd.Series, current: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
        i_safe = current.astype(float).replace(0, np.nan)
        z = voltage.astype(float) / i_safe
        return np.real(z.values), np.imag(z.values)


# ==========================================
# Step 3: Plotly Visualization Functions
# ==========================================

def get_phase_analog_columns(df: pd.DataFrame, selected_phases: List[str]) -> List[str]:
    return [col for col in df.columns if col.startswith(ANALOG_PREFIX) and any(phase in col for phase in selected_phases)]


def get_digital_columns(df: pd.DataFrame) -> List[str]:
    return [col for col in df.columns if col.startswith(DIGITAL_PREFIX)]


def create_analog_layover_plot(
    all_data: Dict[str, pd.DataFrame],
    selected_phases: List[str],
    show_rms: bool,
    sys_freq: float,
) -> go.Figure:
    fig = go.Figure()
    palette = {"Local Main-1": "#1f77b4", "Local Main-2": "#2ca02c", "Remote End": "#d62728"}

    for group, df in all_data.items():
        color = palette.get(group, None)
        columns = get_phase_analog_columns(df, selected_phases)

        for col in columns:
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[col],
                    name=f"{group} {col[2:]}",
                    mode="lines",
                    line={"color": color, "width": 1.75},
                    hovertemplate="%{x:.6f}s<br>%{y:.3f}<extra>%{fullData.name}</extra>",
                )
            )
            if show_rms:
                rms = AnalysisTools.true_rms(df[col], sys_freq, float(df["sampling_rate"].iloc[0]))
                fig.add_trace(
                    go.Scatter(
                        x=df["timestamp"],
                        y=rms,
                        name=f"{group} RMS {col[2:]}",
                        mode="lines",
                        line={"color": color, "dash": "dash", "width": 2},
                        opacity=0.9,
                    )
                )

    fig.update_layout(
        title="Analog Layover: Current / Voltage",
        xaxis_title="Time (s)",
        yaxis_title="Amplitude",
        height=520,
        hovermode="x unified",
        legend_title_text="Traces",
        template="plotly_white",
    )
    fig.update_xaxes(showspikes=True, spikethickness=1)
    fig.update_yaxes(showspikes=True, spikethickness=1)
    return fig


def create_digital_step_plot(all_data: Dict[str, pd.DataFrame]) -> go.Figure:
    fig = go.Figure()
    row_offset = 0

    for group, df in all_data.items():
        digital_cols = get_digital_columns(df)
        for col in digital_cols:
            y = df[col].astype(float) * 0.8 + row_offset
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=y,
                    name=f"{group} {col[2:]}",
                    mode="lines",
                    line={"shape": "hv", "width": 2},
                    hovertemplate="%{x:.6f}s<br>%{y:.0f}<extra>%{fullData.name}</extra>",
                )
            )
            row_offset += 1.0

    fig.update_layout(
        title="Digital Event Timeline",
        xaxis_title="Time (s)",
        yaxis_title="Digital State",
        height=320,
        legend_title_text="Digital Signals",
        template="plotly_white",
    )
    fig.update_yaxes(showticklabels=False)
    return fig


def create_fft_plot(x: np.ndarray, y: np.ndarray, title: str) -> go.Figure:
    return go.Figure(
        data=[go.Bar(x=x, y=y, marker_color="#636efa")],
        layout={
            "title": title,
            "xaxis": {"title": "Frequency (Hz)"},
            "yaxis": {"title": "Magnitude"},
            "template": "plotly_white",
            "height": 420,
        },
    )


def create_impedance_plot(r: np.ndarray, x: np.ndarray) -> go.Figure:
    return go.Figure(
        data=[
            go.Scatter(
                x=r,
                y=x,
                mode="lines+markers",
                marker={"size": 6, "color": "#ef553b"},
            )
        ],
        layout={
            "title": "Impedance Trajectory (R-X)",
            "xaxis": {"title": "Real(Z)"},
            "yaxis": {"title": "Imag(Z)"},
            "template": "plotly_white",
            "height": 420,
        },
    )


# ==========================================
# Step 2: Streamlit UI Layout
# ==========================================

def load_group_data(group_name: str) -> Optional[Tuple[pd.DataFrame, float]]:
    cfg = st.sidebar.file_uploader(f"{group_name} CFG", type=["cfg"], key=f"cfg_{group_name}")
    dat = st.sidebar.file_uploader(f"{group_name} DAT", type=["dat"], key=f"dat_{group_name}")
    offset_ms = st.sidebar.number_input(f"{group_name} offset (ms)", value=0.0, step=0.1, key=f"offset_{group_name}")

    if cfg is not None and dat is not None:
        parser = ComtradeParser()
        try:
            df = parser.load_pair(cfg, dat)
            df["timestamp"] = df["timestamp"] + offset_ms / 1000.0
            return df, offset_ms
        except Exception as exc:
            st.sidebar.error(f"Failed to load {group_name}: {exc}")
    return None


def main() -> None:
    st.set_page_config(page_title="DR Analysis Dashboard", layout="wide")
    st.title("Disturbance Recorder Analysis")
    st.markdown(
        "Use this dashboard to upload and compare multiple COMTRADE relay records (Main-1, Main-2, Remote End)."
    )

    st.sidebar.header("Settings")
    system_frequency = st.sidebar.radio("System Frequency", [50.0, 60.0], index=0)
    st.sidebar.markdown("---")
    st.sidebar.write("Upload one CFG/DAT pair for each relay group and apply an optional time offset to synchronize events.")

    group_names = ["Local Main-1", "Local Main-2", "Remote End"]
    loaded_groups: Dict[str, pd.DataFrame] = {}

    for group_name in group_names:
        with st.sidebar.expander(group_name, expanded=False):
            loaded = load_group_data(group_name)
            if loaded is not None:
                loaded_groups[group_name] = loaded[0]

    if not loaded_groups:
        st.info("Upload at least one COMTRADE pair to begin visualization.")
        return

    available_phases = ["Phase A", "Phase B", "Phase C", "Neutral"]
    selected_phases = st.multiselect("Select phases to display", available_phases, default=["Phase A"])
    show_rms = st.checkbox("Show true RMS", value=False)

    st.subheader("Analog Layover")
    st.plotly_chart(
        create_analog_layover_plot(loaded_groups, selected_phases, show_rms, system_frequency),
        use_container_width=True,
    )

    st.subheader("Digital Event Plot")
    st.plotly_chart(create_digital_step_plot(loaded_groups), use_container_width=True)

    st.markdown("---")
    st.subheader("Advanced Analysis Tools")
    analysis_group = st.selectbox("Choose a dataset for analysis", list(loaded_groups.keys()))
    dataset = loaded_groups[analysis_group]

    if dataset is not None:
        time_min = float(dataset["timestamp"].min())
        time_max = float(dataset["timestamp"].max())
        selected_timerange = st.slider(
            "FFT window range (seconds)",
            min_value=time_min,
            max_value=time_max,
            value=(time_min, min(time_min + 0.1, time_max)),
            step=max((time_max - time_min) / 1000.0, 0.001),
        )

        mask = (dataset["timestamp"] >= selected_timerange[0]) & (dataset["timestamp"] <= selected_timerange[1])
        window_df = dataset.loc[mask]

        if len(window_df) < 4:
            st.warning("Select a larger window for FFT analysis.")
        else:
            phase_columns = get_phase_analog_columns(dataset, ["Phase A", "Phase B", "Phase C"])
            ia_col = next((c for c in phase_columns if "Phase_A" in c and "IA" in c.upper()), phase_columns[0] if phase_columns else None)
            ib_col = next((c for c in phase_columns if "Phase_B" in c and "IB" in c.upper()), None)
            ic_col = next((c for c in phase_columns if "Phase_C" in c and "IC" in c.upper()), None)

            st.markdown("#### FFT Spectrum")
            if ia_col is not None:
                xf, mags = AnalysisTools.fft_spectrum(window_df["timestamp"].values, window_df[ia_col].values)
                st.plotly_chart(create_fft_plot(xf, mags, f"FFT - {analysis_group} / {ia_col[2:]}") , use_container_width=True)
            else:
                st.info("No Phase A current channel detected for FFT.")

            st.markdown("#### Symmetrical Components")
            if ia_col and ib_col and ic_col:
                comps = AnalysisTools.symmetrical_components(dataset[ia_col], dataset[ib_col], dataset[ic_col])
                seq_df = pd.DataFrame(
                    {
                        "positive": np.abs(comps["positive"]),
                        "negative": np.abs(comps["negative"]),
                        "zero": np.abs(comps["zero"]),
                    }
                )
                st.line_chart(seq_df)
            else:
                st.info("Symmetrical component calculation requires three phase current channels.")

            st.markdown("#### Impedance Trajectory")
            voltage_cols = [c for c in dataset.columns if c.startswith(ANALOG_PREFIX) and "PHASE_A" in c and "V" in c.upper()]
            current_cols = [c for c in dataset.columns if c.startswith(ANALOG_PREFIX) and "PHASE_A" in c and "I" in c.upper()]
            if voltage_cols and current_cols:
                r, x = AnalysisTools.impedance_trajectory(dataset[voltage_cols[0]], dataset[current_cols[0]])
                st.plotly_chart(create_impedance_plot(r, x), use_container_width=True)
            else:
                st.info("Impedance trajectory requires one voltage and one current channel for the same phase.")


if __name__ == "__main__":
    main()
