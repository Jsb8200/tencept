import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="TENCEPT | Options Flow Intelligence", page_icon="◈", layout="wide")

st.markdown("""
<style>
.stApp{background:#07111f;color:#e7edf5}
[data-testid="stSidebar"]{background:#091827;border-right:1px solid #1b3045}
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1800px}
[data-testid="stMetric"]{background:#0d1c2d;border:1px solid #20364b;padding:12px 14px;border-radius:10px}
[data-testid="stMetricValue"]{color:#edf4ff}
[data-testid="stMetricLabel"]{color:#9fb1c5}
div[data-testid="stFileUploader"]{background:#0d1c2d;border:1px dashed #36516c;border-radius:10px;padding:8px}
.stButton>button{background:#1769e0;color:white;border:0;border-radius:8px}
hr{border-color:#20364b}
.small-muted{color:#91a4ba;font-size:.82rem}
</style>
""", unsafe_allow_html=True)

PANEL="#0b1928"; GRID="#203247"; TEXT="#dce7f4"; GREEN="#19c784"; RED="#ff5364"; BLUE="#3188ff"

def clean_num(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[$,% ,]","",regex=True),errors="coerce")

def load_files(files):
    frames=[]
    for file in files:
        try:
            d=pd.read_csv(file,low_memory=False); d["__source_file"]=file.name; frames.append(d)
        except Exception as exc:
            st.error(f"Could not read {file.name}: {exc}")
    return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()

def prepare(raw):
    required=["Ticker","Days Until Expiration","Strike Price","Contract Type","Reference Price",
              "Size","Premium Price","Delta","Side Code","Trade Time","Trade Type","Trade ID"]
    missing=[c for c in required if c not in raw.columns]
    if missing: raise ValueError("Missing required columns: "+", ".join(missing))
    d=raw.copy()
    for c in ["Days Until Expiration","Strike Price","Reference Price","Size","Premium Price","Delta",
              "Option Price","Ask Price","Bid Price"]:
        d[c+"_n"]=clean_num(d[c]) if c in d else np.nan
    d["premium_usd"]=d["Size_n"]*d["Option Price_n"]*100
    d["premium_usd"]=d["premium_usd"].where(d["premium_usd"].notna(),d["Premium Price_n"])
    d["Ticker"]=d["Ticker"].astype(str).str.upper().str.strip()
    d["Contract Type"]=d["Contract Type"].astype(str).str.upper().str.strip()
    d["Side Code"]=d["Side Code"].astype(str).str.upper().str.strip()
    d["side_group"]=d["Side Code"].map({"AA":"BUY","A":"BUY","B":"SELL","BB":"SELL","M":"MID"}).fillna("UNCLASSIFIED")
    d["side_sign"]=d["Side Code"].map({"AA":1,"A":1,"B":-1,"BB":-1,"M":0}).fillna(0)
    d["spread_leg"]=d["Trade Type"].astype(str).str.contains("SPRD",case=False,na=False)
    d["signed_delta"]=d["Size_n"]*100*d["Delta_n"]*d["side_sign"]
    d["gross_abs_delta"]=d["Size_n"]*100*d["Delta_n"].abs()
    d["delta_notional"]=d["signed_delta"]*d["Reference Price_n"]
    d["trade_dt"]=pd.to_datetime(d["Trade Time"],utc=True,errors="coerce").dt.tz_convert("America/New_York")
    d["session"]=d["trade_dt"].dt.strftime("%Y-%m-%d")
    d["dte_bucket"]=pd.cut(d["Days Until Expiration_n"],[-.01,1,3,7],labels=["0–1","2–3","4–7"])
    d["buyer_premium"]=np.where(d["side_group"].eq("BUY"),d["premium_usd"],0.0)
    d["seller_premium"]=np.where(d["side_group"].eq("SELL"),d["premium_usd"],0.0)
    d["net_premium"]=d["buyer_premium"]-d["seller_premium"]
    return d

def dark(fig,height=390):
    fig.update_layout(template="plotly_dark",paper_bgcolor=PANEL,plot_bgcolor=PANEL,
        font=dict(color=TEXT,family="Inter,Arial"),height=height,margin=dict(l=18,r=18,t=55,b=30),
        legend=dict(orientation="h",y=1.12),
        xaxis=dict(gridcolor=GRID,zerolinecolor=GRID),yaxis=dict(gridcolor=GRID,zerolinecolor=GRID))
    return fig

def show(fig,height=390):
    st.plotly_chart(dark(fig,height),use_container_width=True)

st.markdown("<div style='font-size:29px;letter-spacing:7px;font-weight:750'>TENCEPT</div><div class='small-muted' style='letter-spacing:2px'>OPTIONS FLOW INTELLIGENCE  /  QUANTDATA CSV ANALYTICS</div>",unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## DATA INPUT")
    uploads=st.file_uploader("Upload QuantData options-flow CSVs",type=["csv"],accept_multiple_files=True)
    st.caption("Upload multiple sessions together. Duplicate Trade IDs are removed from combined calculations.")
    st.divider()
    st.markdown("## NAVIGATION")
    page=st.radio("Workspace",["Overview","Premium Intelligence","Delta & Order Flow","Historical Intelligence","Trade Explorer"],label_visibility="collapsed")
    st.divider()
    st.markdown("## GLOBAL FILTERS")

raw=load_files(uploads) if uploads else pd.DataFrame()
if raw.empty:
    st.title("Welcome to TENCEPT")
    st.info("Upload one or more QuantData Options Order Flow CSV exports in the sidebar. Your five-page workspace will appear here.")
    st.markdown("**Workspace:** Overview · Premium Intelligence · Delta & Order Flow · Historical Intelligence · Trade Explorer")
    st.stop()

try: data=prepare(raw)
except Exception as exc:
    st.error(str(exc)); st.stop()

dupes=int(data["Trade ID"].duplicated().sum())
data=data.drop_duplicates(subset=["Trade ID"],keep="first")
tickers=sorted(data["Ticker"].dropna().unique().tolist())
with st.sidebar:
    preferred=["MU","QQQ","NVDA"]
    defaults=[x for x in preferred if x in tickers]
    ticker=st.selectbox("Ticker",tickers,index=tickers.index(defaults[0]) if defaults else 0)
    dates=sorted(data["session"].dropna().unique())
    if dates:
        dr=st.date_input("Session date range",value=(pd.to_datetime(dates[0]).date(),pd.to_datetime(dates[-1]).date()))
        if isinstance(dr,tuple) and len(dr)==2: start,end=[x.strftime("%Y-%m-%d") for x in dr]
        else: start=end=dr.strftime("%Y-%m-%d")
    else: start=end=""
    dte=st.selectbox("DTE range",["0–7","0–1","2–3","4–7","All"],index=0)
    include_spreads=st.toggle("Include spread legs",value=False)
    st.caption(f"{dupes:,} duplicate Trade IDs removed")
    st.download_button("Download filtered source",data[data["Ticker"].eq(ticker)].to_csv(index=False).encode(),
                       f"{ticker}_source_rows.csv","text/csv",use_container_width=True)

f=data[data["Ticker"].eq(ticker)].copy()
if start and end: f=f[f["session"].between(start,end)]
if dte!="All":
    lo,hi={"0–7":(0,7),"0–1":(0,1),"2–3":(2,3),"4–7":(4,7)}[dte]
    f=f[f["Days Until Expiration_n"].between(lo,hi)]
if not include_spreads: f=f[~f["spread_leg"]]
if f.empty: st.warning("No records match the selected ticker and global filters."); st.stop()

spot_rows=f.dropna(subset=["trade_dt","Reference Price_n"]).sort_values("trade_dt")
spot=float(spot_rows["Reference Price_n"].iloc[-1]) if not spot_rows.empty else np.nan
net=f["signed_delta"].sum(); gross=f["gross_abs_delta"].sum(); premium=f["premium_usd"].sum()
contracts=f["Size_n"].sum(); sessions=f["session"].nunique()
buy_delta=f.loc[f.side_group.eq("BUY"),"signed_delta"].sum()
sell_delta=f.loc[f.side_group.eq("SELL"),"signed_delta"].sum()
by=f.groupby(["Strike Price_n","Contract Type"],dropna=False).agg(
    net_delta=("signed_delta","sum"),gross_delta=("gross_abs_delta","sum"),
    premium=("premium_usd","sum"),trades=("Trade ID","count"),contracts=("Size_n","sum")).reset_index()
calls=by[by["Contract Type"].eq("CALL")]; puts=by[by["Contract Type"].eq("PUT")]
pstrike=f.groupby(["Strike Price_n","Contract Type"],dropna=False).agg(
    premium_dollars=("premium_usd","sum"),buyer_premium=("buyer_premium","sum"),
    seller_premium=("seller_premium","sum"),net_premium=("net_premium","sum"),
    contracts=("Size_n","sum"),trades=("Trade ID","count"),
    avg_option_price=("Option Price_n","mean"),min_option_price=("Option Price_n","min"),
    max_option_price=("Option Price_n","max"),latest_option_price=("Option Price_n","last")).reset_index()
pstrike["buyer_share_pct"]=np.where((pstrike.buyer_premium+pstrike.seller_premium)>0,
    pstrike.buyer_premium/(pstrike.buyer_premium+pstrike.seller_premium)*100,np.nan)

st.markdown(f"## {page}  <span style='font-size:13px;color:#8fa6bf'> {ticker} · {dte} DTE · {sessions} sessions</span>",unsafe_allow_html=True)
metric_cols=st.columns(5)
for col,label,value in zip(metric_cols,["Underlying","Premium traded","Contracts","Net signed delta","Sessions"],
    [f"${spot:,.2f}" if np.isfinite(spot) else "N/A",f"${premium/1e6:,.2f}M",f"{contracts:,.0f}",f"{net/1e3:,.1f}K",str(sessions)]):
    col.metric(label,value)

if page=="Overview":
    st.caption("A compact market-flow overview for the selected ticker and global filters.")
    a,b=st.columns(2)
    with a:
        fig=go.Figure()
        fig.add_trace(go.Bar(y=calls["Strike Price_n"],x=calls["net_delta"],orientation="h",name="Calls",marker_color=GREEN))
        fig.add_trace(go.Bar(y=puts["Strike Price_n"],x=puts["net_delta"],orientation="h",name="Puts",marker_color=RED))
        fig.add_vline(x=0,line_color="#9aacc0")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        fig.update_layout(title="Net Delta by Strike",barmode="relative",xaxis_title="Delta-equivalent contracts",yaxis_title="Strike")
        show(fig)
    with b:
        fig=px.bar(pstrike,x="premium_dollars",y="Strike Price_n",color="Contract Type",orientation="h",
                   color_discrete_map={"CALL":GREEN,"PUT":RED},title="Premium Dollars by Strike")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        fig.update_layout(xaxis_title="Estimated premium traded ($)",yaxis_title="Strike")
        show(fig)
    c,d=st.columns(2)
    with c:
        side=f.groupby("side_group").agg(delta=("signed_delta","sum"),premium=("premium_usd","sum")).reset_index()
        fig=px.bar(side,x="side_group",y="premium",color="side_group",title="Premium by Aggressor Classification",
                   color_discrete_map={"BUY":GREEN,"SELL":RED,"MID":"#9aa8b8","UNCLASSIFIED":"#718096"})
        show(fig,330)
    with d:
        st.markdown("### Highest premium strike cohorts")
        st.dataframe(pstrike.sort_values("premium_dollars",ascending=False).head(15),use_container_width=True,hide_index=True)
    st.markdown("### Underlying reference-price path")
    pp=f.dropna(subset=["trade_dt","Reference Price_n"]).copy()
    if not pp.empty:
        pp["bucket"]=pp.trade_dt.dt.floor("15min")
        pp=pp.groupby("bucket")["Reference Price_n"].median().reset_index()
        fig=px.line(pp,x="bucket",y="Reference Price_n",title="Underlying Reference Price · 15-minute median")
        show(fig,320)

elif page=="Premium Intelligence":
    st.caption("Premium dollars and option trade-price snapshots are separate measurements. Aggressor-side classification is an estimate based on QuantData Side Code.")
    left,right=st.columns(2)
    with left:
        fig=px.bar(pstrike,x="premium_dollars",y="Strike Price_n",color="Contract Type",orientation="h",
                   barmode="relative",color_discrete_map={"CALL":GREEN,"PUT":RED},title="Premium Dollars by Strike · Calls vs Puts")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        fig.update_layout(xaxis_title="Estimated premium traded ($)",yaxis_title="Strike"); show(fig,460)
    with right:
        fig=px.bar(pstrike,x="net_premium",y="Strike Price_n",color="Contract Type",orientation="h",
                   barmode="group",color_discrete_map={"CALL":GREEN,"PUT":RED},title="Net Aggressor-Side Premium")
        fig.add_vline(x=0,line_color="#9aacc0")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        fig.update_layout(xaxis_title="Buyer premium − seller premium ($)",yaxis_title="Strike"); show(fig,460)
    st.markdown("### Option contract price activity")
    st.caption("Observed trade-price snapshots; not a continuous quote series. For precise contract comparisons, filter by expiration and strike.")
    price_rows=f.dropna(subset=["trade_dt","Option Price_n","Strike Price_n"]).sort_values("trade_dt").copy()
    if not price_rows.empty:
        price_rows["time_bucket"]=price_rows.trade_dt.dt.floor("15min")
        top=price_rows.groupby(["Strike Price_n","Contract Type"])["premium_usd"].sum().nlargest(10).index
        price_rows["key"]=list(zip(price_rows["Strike Price_n"],price_rows["Contract Type"]))
        ts=price_rows[price_rows.key.isin(top)].groupby(["time_bucket","Strike Price_n","Contract Type"])["Option Price_n"].median().reset_index()
        if not ts.empty:
            ts["series"]=ts["Strike Price_n"].astype(str)+" "+ts["Contract Type"]
            fig=px.line(ts,x="time_bucket",y="Option Price_n",color="series",title="15-minute Median Observed Trade Price",
                        labels={"time_bucket":"Time (ET)","Option Price_n":"Option price ($)","series":"Strike / type"})
            show(fig,420)
        summary=price_rows.groupby(["Strike Price_n","Contract Type"]).agg(
            first_observed=("Option Price_n","first"),latest_observed=("Option Price_n","last"),
            low_trade=("Option Price_n","min"),high_trade=("Option Price_n","max"),
            mean_trade=("Option Price_n","mean"),trades=("Trade ID","count"),
            premium=("premium_usd","sum")).reset_index()
        summary["observed_change"]=summary.latest_observed-summary.first_observed
        st.dataframe(summary.sort_values("premium",ascending=False).head(100),use_container_width=True,hide_index=True)
    else: st.info("Option Price values or valid timestamps are unavailable for these filtered rows.")
    st.markdown("### Strike premium detail")
    st.dataframe(pstrike.sort_values("premium_dollars",ascending=False),use_container_width=True,hide_index=True)
    st.download_button("Download strike premium CSV",pstrike.to_csv(index=False).encode(),f"{ticker}_strike_premium.csv","text/csv")

elif page=="Delta & Order Flow":
    st.caption("Signed delta-equivalent contracts = Size × 100 × option delta × aggressor sign. This is an estimated aggressor-side measure, not dealer inventory.")
    a,b=st.columns(2)
    with a:
        fig=go.Figure()
        fig.add_trace(go.Bar(y=calls["Strike Price_n"],x=calls["net_delta"],orientation="h",name="Calls",marker_color=GREEN))
        fig.add_trace(go.Bar(y=puts["Strike Price_n"],x=puts["net_delta"],orientation="h",name="Puts",marker_color=RED))
        fig.add_vline(x=0,line_color="#9aacc0")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        fig.update_layout(title="Strike Delta Profile",barmode="relative",xaxis_title="Delta-equivalent contracts",yaxis_title="Strike"); show(fig,450)
    with b:
        side=f.groupby(["Strike Price_n","side_group"])["signed_delta"].sum().reset_index()
        fig=px.bar(side,x="signed_delta",y="Strike Price_n",color="side_group",orientation="h",
                   color_discrete_map={"BUY":GREEN,"SELL":RED,"MID":"#9aa8b8","UNCLASSIFIED":"#718096"},
                   title="Bid/Ask Aggressor Delta by Strike")
        fig.add_vline(x=0,line_color="#9aacc0")
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dash",line_color="white",annotation_text=f"Underlying ${spot:.2f}")
        show(fig,450)
    st.markdown("### Delta heatmap · strike × 15-minute bucket")
    hd=f.dropna(subset=["trade_dt","Strike Price_n"]).copy()
    hd["bucket"]=hd.trade_dt.dt.floor("15min").dt.strftime("%m-%d %H:%M")
    hp=hd.pivot_table(index="Strike Price_n",columns="bucket",values="signed_delta",aggfunc="sum",fill_value=0).sort_index(ascending=False)
    if not hp.empty:
        fig=go.Figure(go.Heatmap(z=hp.values,x=hp.columns,y=hp.index,colorscale=[[0,"#ef4658"],[.5,"#101d2b"],[1,"#16c784"]],colorbar=dict(title="Signed Δ")))
        pr=hd.groupby("bucket")["Reference Price_n"].median().reindex(hp.columns)
        fig.add_trace(go.Scatter(x=hp.columns,y=pr.values,mode="lines",name="Underlying reference price",line=dict(color="white",width=2.5)))
        if np.isfinite(spot): fig.add_hline(y=spot,line_dash="dot",line_color="#8fbaff",annotation_text=f"Last ${spot:.2f}")
        fig.update_layout(title="Signed Delta Heatmap + Underlying Reference Price",xaxis_title="Time (ET)",yaxis_title="Strike / reference price")
        show(fig,480)
    st.markdown("### Price vs cumulative delta")
    timeline=hd.sort_values("trade_dt").copy()
    if not timeline.empty:
        timeline["cum_delta"]=timeline["signed_delta"].cumsum()
        timeline["bucket"]=timeline.trade_dt.dt.floor("15min")
        tl=timeline.groupby("bucket").agg(cum_delta=("cum_delta","last"),underlying=("Reference Price_n","median")).reset_index()
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=tl.bucket,y=tl.cum_delta,name="Cumulative signed delta",line=dict(color=BLUE)))
        fig.add_trace(go.Scatter(x=tl.bucket,y=tl.underlying,name="Underlying reference price",yaxis="y2",line=dict(color="white")))
        fig.update_layout(title="Cumulative Signed Delta vs Underlying",xaxis_title="Time (ET)",
                          yaxis=dict(title="Cumulative delta"),yaxis2=dict(title="Underlying price",overlaying="y",side="right"))
        show(fig,380)

elif page=="Historical Intelligence":
    st.caption("Historical comparisons use the selected date range and the same ticker, DTE and spread filters.")
    hist=f.dropna(subset=["session","Strike Price_n"]).groupby(["session","Strike Price_n"])["signed_delta"].sum().reset_index()
    a,b=st.columns(2)
    with a:
        hp=hist.pivot(index="Strike Price_n",columns="session",values="signed_delta").fillna(0).sort_index(ascending=False)
        if not hp.empty:
            fig=px.imshow(hp,aspect="auto",color_continuous_scale=["#ef4658","#101d2b","#16c784"],origin="upper",title="Historical Strike Delta Migration")
            show(fig,450)
    with b:
        hm=f.dropna(subset=["session","Strike Price_n"]).groupby(["session","Strike Price_n"]).agg(
            premium=("premium_usd","sum"),gross_delta=("gross_abs_delta","sum"),net_delta=("signed_delta","sum")).reset_index()
        if not hm.empty:
            fig=px.scatter(hm,x="premium",y="net_delta",color="session",size="gross_delta",
                           hover_data=["Strike Price_n"],title="Session Premium vs Net Delta by Strike")
            show(fig,450)
    pg=f.dropna(subset=["session","Strike Price_n","dte_bucket"]).groupby(
        ["Strike Price_n","Contract Type","dte_bucket","session"],observed=True).agg(
        net_delta=("signed_delta","sum"),gross=("gross_abs_delta","sum"),premium=("premium_usd","sum")).reset_index()
    if not pg.empty:
        ps=pg.groupby(["Strike Price_n","Contract Type","dte_bucket"],observed=True).agg(
            active_sessions=("session","nunique"),positive_sessions=("net_delta",lambda x:int((x>0).sum())),
            negative_sessions=("net_delta",lambda x:int((x<0).sum())),cumulative_gross=("gross","sum"),
            cumulative_premium=("premium","sum"),net_delta=("net_delta","sum")).reset_index()
        ps["coverage_pct"]=ps.active_sessions/max(1,sessions)*100
        ps["direction_consistency_pct"]=np.maximum(ps.positive_sessions,ps.negative_sessions)/ps.active_sessions*100
        st.markdown("### Strike persistence")
        st.dataframe(ps.sort_values(["active_sessions","cumulative_gross"],ascending=False).head(100),use_container_width=True,hide_index=True)
        st.download_button("Download persistence ranking",ps.to_csv(index=False).encode(),f"{ticker}_persistence.csv","text/csv")
    daily=f.dropna(subset=["session","Strike Price_n","dte_bucket"]).groupby(
        ["session","Strike Price_n","Contract Type","dte_bucket"],observed=True).agg(
        premium=("premium_usd","sum"),signed_delta=("signed_delta","sum"),gross_delta=("gross_abs_delta","sum")).reset_index()
    ss=sorted(daily.session.unique())
    if len(ss)>=2:
        prev,cur=ss[-2],ss[-1]; keys=["Strike Price_n","Contract Type","dte_bucket"]
        old=daily[daily.session.eq(prev)].set_index(keys); new=daily[daily.session.eq(cur)].set_index(keys); idx=old.index.union(new.index)
        comp=pd.DataFrame(index=idx)
        for col in ["premium","signed_delta","gross_delta"]:
            comp[col+"_prev"]=old[col].reindex(idx).fillna(0); comp[col+"_current"]=new[col].reindex(idx).fillna(0)
            comp[col+"_change"]=comp[col+"_current"]-comp[col+"_prev"]
        comp=comp.reset_index()
        st.markdown(f"### Adjacent-session migration · {prev} → {cur}")
        fig=px.scatter(comp,x="premium_change",y="signed_delta_change",color="Contract Type",
                       hover_data=["Strike Price_n","dte_bucket"],title="Premium change vs signed-delta change")
        fig.add_hline(y=0,line_color="#9aacc0"); fig.add_vline(x=0,line_color="#9aacc0"); show(fig,390)
        st.dataframe(comp.sort_values("premium_change",key=lambda x:x.abs(),ascending=False).head(60),use_container_width=True,hide_index=True)
    latest=daily[daily.session.eq(ss[-1])] if ss else daily.iloc[0:0]
    if not latest.empty:
        overlap=latest.pivot_table(index="Strike Price_n",columns="Contract Type",values="premium",aggfunc="sum",fill_value=0)
        for typ in ["CALL","PUT"]:
            if typ not in overlap: overlap[typ]=0
        overlap["Both call & put active"]=(overlap.CALL>0)&(overlap.PUT>0)
        st.markdown("### Same-strike call / put overlap")
        st.dataframe(overlap[overlap["Both call & put active"]].reset_index(),use_container_width=True,hide_index=True)
        st.caption("Both-side activity does not establish a paired strategy or common participant.")

elif page=="Trade Explorer":
    st.caption("Inspect the underlying trade records. Use the global filters in the sidebar to narrow the dataset.")
    q=st.text_input("Search trade ID, strike, expiration or side code")
    view=f.copy()
    if q:
        mask=pd.Series(False,index=view.index)
        for col in ["Trade ID","Strike Price","Expiration Date","Side Code","Contract Type"]:
            if col in view: mask=mask|view[col].astype(str).str.contains(q,case=False,na=False)
        view=view[mask]
    showcols=[c for c in ["Trade Time","Ticker","Expiration Date","Days Until Expiration","Strike Price","Contract Type",
        "Side Code","Size","Option Price","Premium Price","Delta","Trade Type","Consolidation Type",
        "Is Opening Position","Trade ID"] if c in view.columns]
    st.dataframe(view[showcols].sort_values("Trade Time",ascending=False).head(2000),use_container_width=True,hide_index=True)
    st.download_button("Download explorer results",view[showcols].to_csv(index=False).encode(),f"{ticker}_trade_explorer.csv","text/csv")
    st.caption("Showing up to 2,000 rows in the table; CSV download contains all matching rows.")

st.divider()
st.markdown("<div class='small-muted'>Method note: AA/A = buyer-initiated; B/BB = seller-initiated; M = neutral. Premium dollars = contracts × option trade price × 100, with QuantData Premium Price as fallback. These are trade-flow estimates, not confirmed opening positions, dealer inventory or hedge flow. Reference Price is a trade-level snapshot, not independent continuous OHLC data.</div>",unsafe_allow_html=True)
