import streamlit as st
import pandas as pd
from datetime import date, time
from supabase import create_client, Client

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Health & Supplements Log", page_icon="💊", layout="centered")
st.title("💊 Health & Supplements Log")

# -----------------------------
# Connect to Supabase (filled via Streamlit Secrets)
# -----------------------------
SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["service_role_key"]  # kept private on the server
sb: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TABLE = "health_logs"

EFFICACY_SCALE = [1,2,3,4,5,6,7,8,9,10]
SUPPLEMENT_OPTIONS = [
    "Essential Capsules",
    "Advanced Antioxidants",
    "NAC Ginger Curcumin",
    "Red Yeast Rice Garlic",
]

NUMERIC_SERIES_FOR_CHARTS = [
    ("Sleep (hrs)", "sleep_hours"),
    ("Sunlight (hrs)", "sunlight_hours"),
    ("Workout intensity", "workout_intensity"),
    ("AM efficacy", "am_med_efficacy"),
    ("Afternoon efficacy", "afternoon_med_efficacy"),
    ("PM efficacy", "pm_med_efficacy"),
]

def load_df():
    res = sb.table(TABLE).select("*").order("date").execute()
    data = res.data or []
    df = pd.DataFrame(data)
    if df.empty:
        return pd.DataFrame(columns=[
            "id","created_at","date","supplement","sleep_hours","melatonin_taken","melatonin_mg",
            "wake_time","workout","workout_intensity","breakfast","sunlight_hours","lunch","snack",
            "dinner","dinner_time","supplement_time","initial_reaction","morning_mood",
            "am_med_efficacy","afternoon_med_efficacy","pm_med_efficacy","notes"
        ])
    # Parse types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for c in ["wake_time","dinner_time","supplement_time"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.time
    # Coerce numerics
    for c in ["sleep_hours","melatonin_mg","sunlight_hours","workout_intensity",
              "am_med_efficacy","afternoon_med_efficacy","pm_med_efficacy"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def save_row(rec: dict):
    payload = {k: (v if v != "" else None) for k, v in rec.items()}
    return sb.table(TABLE).insert(payload).execute()

# -----------------------------
# Entry form
# -----------------------------
with st.form("entry"):
    col1, col2 = st.columns(2)
    with col1:
        dte = st.date_input("Date", value=date.today())
        supplement = st.selectbox("Supplement", SUPPLEMENT_OPTIONS, index=0)

        sleep_hours = st.number_input("Sleep hours", min_value=0.0, max_value=24.0, step=0.5)

        melatonin_taken = st.checkbox("Took melatonin?")
        melatonin_mg = st.number_input("Melatonin mg", min_value=0.0, max_value=20.0, step=0.5,
                                       disabled=not melatonin_taken)

        wake_time = st.time_input("Wake time", value=time(6,0))
        workout = st.checkbox("Workout?")
        workout_intensity = st.slider("Workout intensity (0–10)", 0, 10, 0, disabled=not workout)

        sunlight_hours = st.slider("Sunlight (hours)", 0.0, 12.0, 0.0, 0.5)

    with col2:
        breakfast = st.text_area("Breakfast (what you ate)")
        lunch = st.text_area("Lunch (what you ate)")
        snack = st.text_area("Snack (what you ate)")
        dinner = st.text_area("Dinner (what you ate)")
        dinner_time = st.time_input("Dinner time", value=time(19,0))

        supplement_time = st.time_input("Supplement time", value=time(8,30))
        initial_reaction = st.text_area("Initial reaction to supplement")
        morning_mood = st.text_area("Morning mood (how you feel)")

        am_med_efficacy = st.selectbox("AM med efficacy (1–10)", EFFICACY_SCALE, index=6)
        afternoon_med_efficacy = st.selectbox("Afternoon med efficacy (1–10)", EFFICACY_SCALE, index=6)
        pm_med_efficacy = st.selectbox("PM med efficacy (1–10)", EFFICACY_SCALE, index=6)

        notes = st.text_area("Notes (evening efficacy, anything else)")

    submitted = st.form_submit_button("Save entry")
    if submitted:
        rec = {
            "date": str(dte),
            "supplement": supplement,

            "sleep_hours": float(sleep_hours) if sleep_hours is not None else None,
            "melatonin_taken": bool(melatonin_taken),
            "melatonin_mg": (float(melatonin_mg) if melatonin_taken else None),

            "wake_time": wake_time.strftime("%H:%M:%S") if wake_time else None,
            "workout": bool(workout),
            "workout_intensity": (int(workout_intensity) if workout else None),

            "breakfast": breakfast.strip() or None,
            "sunlight_hours": float(sunlight_hours),
            "lunch": lunch.strip() or None,
            "snack": snack.strip() or None,
            "dinner": dinner.strip() or None,
            "dinner_time": dinner_time.strftime("%H:%M:%S") if dinner_time else None,

            "supplement_time": supplement_time.strftime("%H:%M:%S") if supplement_time else None,
            "initial_reaction": initial_reaction.strip() or None,
            "morning_mood": morning_mood.strip() or None,

            "am_med_efficacy": int(am_med_efficacy),
            "afternoon_med_efficacy": int(afternoon_med_efficacy),
            "pm_med_efficacy": int(pm_med_efficacy),

            "notes": notes.strip() or None,
        }
        save_row(rec)
        st.success("Saved!")

st.markdown("---")
st.subheader("📈 Trends")

df = load_df()
if df.empty:
    st.info("No data yet. Add your first entry!")
else:
    # Filters
    f1, f2 = st.columns(2)
    with f1:
        supp_opts = sorted([s for s in df["supplement"].dropna().unique().tolist()])
        supp_filter = st.multiselect("Filter by Supplement", supp_opts, default=supp_opts)
    with f2:
        dmin = df["date"].min()
        dmax = df["date"].max()
        date_range = st.date_input("Date range", (dmin, dmax))

    mask = (df["supplement"].isin(supp_filter)) & (df["date"] >= date_range[0]) & (df["date"] <= date_range[1])
    v = df.loc[mask].sort_values("date")

    if v.empty:
        st.warning("No records for the selected filters.")
    else:
        # Numeric series chart
        series = pd.DataFrame({"date": v["date"]})
        for label, col in [
            ("Sleep (hrs)", "sleep_hours"),
            ("Sunlight (hrs)", "sunlight_hours"),
            ("Workout intensity", "workout_intensity"),
            ("AM efficacy", "am_med_efficacy"),
            ("Afternoon efficacy", "afternoon_med_efficacy"),
            ("PM efficacy", "pm_med_efficacy"),
        ]:
            if col in v.columns:
                series[label] = pd.to_numeric(v[col], errors="coerce")
        series = series.set_index("date")
        st.line_chart(series)

        # Composite performance (normalize available columns and average)
        def norm(s: pd.Series):
            s = pd.to_numeric(s, errors="coerce")
            rng = s.max() - s.min()
            if pd.isna(rng) or rng == 0:
                return pd.Series([0.0]*len(s), index=s.index)
            return (s - s.min()) / rng

        usable_cols = [c for c in ["sleep_hours","sunlight_hours","workout_intensity",
                                   "am_med_efficacy","afternoon_med_efficacy","pm_med_efficacy"] if c in v.columns]
        if usable_cols:
            comp = pd.DataFrame({"date": v["date"]}).set_index("date")
            comp["Composite performance"] = sum([norm(v[c]) for c in usable_cols]) / float(len(usable_cols))
            st.markdown("**Composite performance (normalized 0–1)**")
            st.line_chart(comp)

        with st.expander("See raw entries"):
            st.dataframe(v.sort_values("date", ascending=False), use_container_width=True)
