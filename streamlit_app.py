import streamlit as st
import pandas as pd
import plotly.express as px
import statsmodels


st.set_page_config(
    page_title="IMDB Top 1000",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="metric-container"] { background: #1a1a2e; border-radius: 10px; padding: 12px; }
    [data-testid="metric-container"] label { color: #a0a0b0 !important; font-size: 0.78rem; }
    [data-testid="metric-container"] [data-testid="metric-value"] { font-size: 1.3rem; color: #f0c040; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data(path: str = "imdb_top_1000.csv") -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        st.error(f"Dataset not found at `{path}`. Place `imdb_top_1000.csv` in the same folder.")
        st.stop()

    df["Released_Year"] = pd.to_numeric(
        df["Released_Year"].astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )

    df["Runtime"] = pd.to_numeric(
        df["Runtime"].astype(str).str.extract(r"(\d+)")[0],
        errors="coerce",
    )

    df["Gross"] = pd.to_numeric(
        df["Gross"].astype(str).str.replace(r"[\$,]", "", regex=True),
        errors="coerce",
    )

    df["Main_Genre"] = df["Genre"].astype(str).str.split(",").str[0].str.strip()

    required = {"Series_Title", "Released_Year", "IMDB_Rating", "No_of_Votes", "Main_Genre"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"CSV is missing columns: {missing}")
        st.stop()

    return df


df = load_data()

with st.sidebar:
    st.header("Filters")

    valid_years = df["Released_Year"].dropna()
    year_range = st.slider(
        "Release Year",
        min_value=int(valid_years.min()),
        max_value=int(valid_years.max()),
        value=(int(valid_years.min()), int(valid_years.max())),
    )

    genres = ["All"] + sorted(df["Main_Genre"].dropna().unique().tolist())
    selected_genre = st.selectbox("Genre", genres)

    valid_ratings = df["IMDB_Rating"].dropna()
    min_rating = st.slider(
        "Minimum Rating",
        min_value=float(valid_ratings.min()),
        max_value=float(valid_ratings.max()),
        value=float(valid_ratings.min()),
        step=0.1,
    )

    search = st.text_input("Search by title")

mask = (
    df["Released_Year"].between(*year_range)
    & (df["IMDB_Rating"] >= min_rating)
)
filtered = df[mask].copy()

if selected_genre != "All":
    filtered = filtered[filtered["Main_Genre"] == selected_genre]

if search.strip():
    filtered = filtered[
        filtered["Series_Title"].str.contains(search.strip(), case=False, na=False)
    ]

if filtered.empty:
    st.warning("No movies match the current filters. Try loosening the criteria.")
    st.stop()

filtered["Decade"] = ((filtered["Released_Year"].dropna() // 10) * 10).astype("Int64")
filtered["Decade"] = filtered["Released_Year"].apply(
    lambda y: int((y // 10) * 10) if pd.notna(y) else pd.NA
)

st.title("IMDB Top 1000 — Dashboard")
st.caption(f"Showing **{len(filtered):,}** movies · filtered from {len(df):,} total")

st.subheader("Key Metrics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Movies", f"{len(filtered):,}")
c2.metric("Avg Rating", f"{filtered['IMDB_Rating'].mean():.2f}")
c3.metric("Avg Runtime", f"{filtered['Runtime'].mean():.0f} min")
gross_total = filtered["Gross"].dropna().sum()
c4.metric("Total Gross", f"${gross_total / 1e9:.2f}B" if gross_total >= 1e9 else f"${gross_total / 1e6:.1f}M")

st.subheader("Insights")
c5, c6, c7, c8 = st.columns(4)

top_movie = filtered.sort_values(["IMDB_Rating", "No_of_Votes"], ascending=False).iloc[0]
most_voted = filtered.loc[filtered["No_of_Votes"].idxmax()]

decade_counts = filtered["Decade"].value_counts()
best_decade = int(decade_counts.idxmax()) if not decade_counts.empty else "N/A"

top_genre = filtered["Main_Genre"].value_counts().idxmax()

c5.metric("Top Rated", top_movie["Series_Title"], f"{top_movie['IMDB_Rating']}")
c6.metric("Most Voted", most_voted["Series_Title"], f"{int(most_voted['No_of_Votes']):,} votes")
c7.metric("Best Decade", f"{best_decade}s" if isinstance(best_decade, int) else best_decade)
c8.metric("Top Genre", top_genre)

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("🎞 Movies per Decade")
    decade_df = (
        filtered.groupby("Decade")
        .size()
        .reset_index(name="Count")
        .dropna(subset=["Decade"])
        .sort_values("Decade")
    )
    decade_df["Decade"] = decade_df["Decade"].astype(int).astype(str) + "s"
    fig1 = px.bar(
        decade_df, x="Decade", y="Count",
        color="Count", color_continuous_scale="oranges",
        labels={"Decade": "Decade", "Count": "# Movies"},
    )
    fig1.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig1, use_container_width=True)

with col_b:
    st.subheader("Top 10 Genres")
    genre_df = (
        filtered["Main_Genre"].value_counts().head(10)
        .reset_index()
        .rename(columns={"index": "Genre", "Main_Genre": "Count"})
    )
    if "Main_Genre" not in genre_df.columns:
        genre_df.columns = ["Genre", "Count"]
    fig2 = px.bar(
        genre_df, x="Genre", y="Count",
        color="Count", color_continuous_scale="teal",
    )
    fig2.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig2, use_container_width=True)

col_c, col_d = st.columns(2)

with col_c:
    st.subheader("Rating vs Votes (log scale)")
    fig3 = px.scatter(
        filtered.dropna(subset=["No_of_Votes", "IMDB_Rating"]),
        x="No_of_Votes", y="IMDB_Rating",
        hover_name="Series_Title",
        hover_data={"Released_Year": True, "Main_Genre": True},
        log_x=True, opacity=0.7,
        color="IMDB_Rating", color_continuous_scale="reds",
    )
    fig3.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

with col_d:
    st.subheader("Runtime vs Rating")
    scatter_df = filtered.dropna(subset=["Runtime", "IMDB_Rating"])
    try:
        trendline = "ols"
    except ImportError:
        trendline = None 
    fig4 = px.scatter(
        scatter_df,
        x="Runtime", y="IMDB_Rating",
        hover_name="Series_Title",
        trendline=trendline, opacity=0.7,
        color="Main_Genre",
    )
    fig4.update_layout(showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

st.subheader("Average Rating Over Time")
yearly = (
    filtered.dropna(subset=["Released_Year", "IMDB_Rating"])
    .groupby("Released_Year")["IMDB_Rating"]
    .agg(["mean", "count"])
    .reset_index()
    .rename(columns={"mean": "Avg_Rating", "count": "Movies"})
)
fig5 = px.line(
    yearly, x="Released_Year", y="Avg_Rating",
    hover_data={"Movies": True},
    labels={"Released_Year": "Year", "Avg_Rating": "Avg Rating"},
    markers=True,
)
fig5.update_traces(line_color="#f0c040")
st.plotly_chart(fig5, use_container_width=True)

if "Director" in filtered.columns:
    st.subheader("Top Directors by Movie Count")
    dir_df = (
        filtered["Director"].value_counts().head(10)
        .reset_index()
        .rename(columns={"index": "Director", "Director": "Count"})
    )
    if "Director" not in dir_df.columns:
        dir_df.columns = ["Director", "Count"]
    fig6 = px.bar(
        dir_df, x="Director", y="Count",
        color="Count", color_continuous_scale="purples",
    )
    fig6.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig6, use_container_width=True)

st.subheader("Top 10 Movies (filtered)")
show_cols = [c for c in ["Series_Title", "Released_Year", "IMDB_Rating",
                          "No_of_Votes", "Main_Genre", "Runtime", "Director"]
             if c in filtered.columns]

top10 = (
    filtered.sort_values(["IMDB_Rating", "No_of_Votes"], ascending=[False, False])
    .head(10)[show_cols]
    .reset_index(drop=True)
)
top10.index += 1  

st.dataframe(top10, use_container_width=True)

st.download_button(
    label="⬇ Download Filtered Data (CSV)",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="imdb_filtered.csv",
    mime="text/csv",
)

st.markdown("## Key Takeaways")
avg_runtime = filtered["Runtime"].mean()
st.markdown(f"""
- **{top_genre}** is the most represented genre in the current selection  
- The **{best_decade}s** produced the highest number of top-rated movies  
- Higher vote counts generally correlate with stronger audience approval  
- Average runtime is **{avg_runtime:.0f} minutes** across the filtered set  
- Total box-office gross (where available): **${gross_total / 1e9:.2f}B**  
""")

st.divider()
st.caption("Built with Streamlit · IMDB Top 1000 Dataset")