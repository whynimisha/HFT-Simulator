import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
import plotly.express as px
import io
import zipfile

st.set_page_config(page_title="HFT Backtest Dashboard", layout="wide")
st.title("📈 HFT Market Making Backtest Dashboard")

# -------------------------------
# Load Data
# -------------------------------
@st.cache_data
def load_data():
    trades, logs = None, None
    trades_path = "artifacts/trades.csv"
    logs_path = "artifacts/logs.csv"
    if os.path.exists(trades_path):
        trades = pd.read_csv(trades_path)
    if os.path.exists(logs_path):
        logs = pd.read_csv(logs_path)
    return trades, logs

trades, logs = load_data()

# -------------------------------
# Trades Overview
# -------------------------------
if trades is not None and not trades.empty:
    st.header("Trades Overview")
    st.metric("Total Trades", len(trades))
    st.dataframe(trades.head(20))

    if "pnl" in trades.columns:
        st.subheader("Trade PnL Distribution")
        fig = px.histogram(trades, x="pnl", nbins=40, title="Trade PnL Distribution")
        fig.update_layout(xaxis_title="PnL", yaxis_title="Frequency")
        st.plotly_chart(fig)

    if "liquidity" in trades.columns:
        st.subheader("Maker vs Taker Split")
        st.bar_chart(trades["liquidity"].value_counts())
else:
    st.error("⚠️ No trades.csv found in artifacts/. Run a backtest first.")
    st.stop()

if len(trades) == 0:
    st.error("⚠️ No trades executed. Check risk manager or config settings.")

# -------------------------------
# Plots & Attribution
# -------------------------------
st.header("Generated Plots & Attribution")
plot_files = glob.glob("artifacts/plots/*.*")
if plot_files:
    for f in plot_files:
        name = os.path.basename(f)
        if f.endswith(".png"):
            st.image(f, caption=name)
        elif f.endswith(".csv"):
            df_plot = pd.read_csv(f)
            st.subheader(name)
            st.dataframe(df_plot.head())
else:
    st.info("No plots found in artifacts/plots/. Run backtest with plotting enabled.")

# -------------------------------
# PnL Attribution (Spread vs Markout vs Fees)
# -------------------------------
attrib_file = "artifacts/plots/attribution_summary.csv"
if os.path.exists(attrib_file):
    st.header("PnL Attribution Analysis")
    df_attr = pd.read_csv(attrib_file)
    if set(["spread", "markout", "fees", "time"]).issubset(df_attr.columns):
        df_attr["time"] = pd.to_datetime(df_attr["time"], errors="coerce")

        st.sidebar.header("Filters")
        start_date = st.sidebar.date_input("Start Date", df_attr["time"].min().date())
        end_date = st.sidebar.date_input("End Date", df_attr["time"].max().date())
        mask = (df_attr["time"].dt.date >= start_date) & (df_attr["time"].dt.date <= end_date)
        df_filtered = df_attr.loc[mask].copy()

        if not df_filtered.empty:
            st.subheader("Cumulative Attribution")
            fig = px.area(df_filtered, x="time", y=["spread", "markout", "fees"], title="PnL Attribution (Cumulative)")
            fig.update_layout(yaxis_title="PnL", legend_title="Components")
            max_pnl_idx = df_filtered[["spread", "markout", "fees"]].cumsum().sum(axis=1).idxmax()
            fig.add_annotation(x=df_filtered.loc[max_pnl_idx, "time"], y=df_filtered[["spread", "markout", "fees"]].cumsum().sum(axis=1).max(),
                               text=f"Max PnL: {df_filtered.loc[max_pnl_idx, ['spread', 'markout', 'fees']].sum():.2f}",
                               showarrow=True, arrowhead=2)
            st.plotly_chart(fig)

            st.subheader("Daily Attribution Breakdown")
            daily_attr = df_filtered.set_index("time").resample("1D")[["spread", "markout", "fees"]].sum()
            fig = px.bar(daily_attr, x=daily_attr.index, y=["spread", "markout", "fees"], title="PnL Attribution per Day",
                         barmode="stack")
            fig.update_layout(xaxis_title="Date", yaxis_title="PnL", xaxis_tickangle=45)
            st.plotly_chart(fig)
            st.dataframe(daily_attr.tail(10))

            st.subheader("PnL Summary")
            total_pnl = df_filtered[["spread", "markout", "fees"]].sum().sum()
            contrib_percent = (df_filtered[["spread", "markout", "fees"]].sum() / total_pnl * 100).round(2).fillna(0)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total PnL", f"{total_pnl:.2f}")
            col2.metric("Spread Contribution", f"{contrib_percent['spread']}%")
            col3.metric("Markout Contribution", f"{contrib_percent['markout']}%")
            st.metric("Fees Contribution", f"{contrib_percent['fees']}% (Negative Impact)")

            st.subheader("Statistical Metrics")
            daily_pnl = daily_attr.sum(axis=1)
            st.write(f"Average Daily PnL: {daily_pnl.mean():.2f}")
            st.write(f"Std Dev Daily PnL: {daily_pnl.std():.2f}")
            st.write(f"Max Daily PnL: {daily_pnl.max():.2f}")
            st.write(f"Min Daily PnL: {daily_pnl.min():.2f}")

            if total_pnl == 0 or pd.isna(total_pnl):
                st.warning("Total PnL is zero or undefined. Check data integrity.")
            elif total_pnl < 0:
                st.error("Overall loss detected. Review strategy parameters.")
            if contrib_percent.sum() == 0:
                st.warning("No significant PnL contributions. Verify trade data.")

            st.download_button("Download Attribution Data", df_filtered.to_csv(index=False),
                               "attribution_summary_filtered.csv", mime="text/csv")
        else:
            st.error("Filtered data is empty. Adjust date range or check input file.")
    else:
        st.warning("Attribution CSV does not contain expected columns: spread, markout, fees, time")
else:
    st.info("No attribution_summary.csv found. Run backtest with attribution enabled.")

# -------------------------------
# Logs Overview
# -------------------------------
if logs is not None and not logs.empty:
    st.header("Logs Overview")
    st.metric("Total Log Entries", len(logs))
    if "time" in logs.columns:
        logs["time"] = pd.to_datetime(logs["time"], errors="coerce")
        if "equity" in logs.columns:
            st.subheader("Equity Curve Over Time")
            fig = px.line(logs, x="time", y="equity", title="Equity Curve Over Time")
            fig.update_layout(yaxis_title="Equity")
            st.plotly_chart(fig)
        if "inventory" in logs.columns:
            st.subheader("Inventory Over Time")
            fig = px.line(logs, x="time", y="inventory", title="Inventory Over Time")
            fig.update_layout(yaxis_title="Inventory")
            st.plotly_chart(fig)
        if "cash" in logs.columns:
            st.subheader("Cash Balance Over Time")
            fig = px.line(logs, x="time", y="cash", title="Cash Balance Over Time")
            fig.update_layout(yaxis_title="Cash")
            st.plotly_chart(fig)
        if logs["equity"].min() < -100:  # Example threshold
            st.warning("⚠️ Equity dropped below -100. Review strategy.")
else:
    st.info("ℹ️ No logs.csv found. To enable logs, update run_backtest.py to save logs.")

# -------------------------------
# Downloads
# -------------------------------
st.header("Download Results")
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
    zip_file.writestr("trades.csv", trades.to_csv(index=False))
    if logs is not None:
        zip_file.writestr("logs.csv", logs.to_csv(index=False))
    if os.path.exists(attrib_file):
        with open(attrib_file, "rb") as f:
            zip_file.writestr("attribution_summary.csv", f.read())
st.download_button("⬇️ Download All Results (Zip)", zip_buffer.getvalue(), "backtest_results.zip")