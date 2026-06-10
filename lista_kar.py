import streamlit as st
import pandas as pd
import gspread
import json
import anthropic
from datetime import datetime
from sklearn.linear_model import LinearRegression
import numpy as np

# Konfiguracja strony
st.set_page_config(page_title="System Alertów i Kosztów CHMURA", page_icon="🚨", layout="centered")

# ==========================================
# 🔑 KONFIGURACJA HASŁA DOSTĘPU
HASLO_DOSTEPU = "123"
# ==========================================

# --- SYSTEM LOGOWANIA ---
if "zalogowano" not in st.session_state:
    st.session_state["zalogowano"] = False

if not st.session_state["zalogowano"]:
    st.title("🔐 Autoryzacja")
    st.write("Ta aplikacja jest zabezpieczona. Podaj hasło firmowe, aby uzyskać dostęp.")

    wpisane_haslo = st.text_input("Wpisz hasło", type="password")
    przycisk_zaloguj = st.button("Zaloguj się")

    if przycisk_zaloguj:
        if wpisane_haslo == HASLO_DOSTEPU:
            st.session_state["zalogowano"] = True
            st.rerun()
        else:
            st.error("❌ Niepoprawne hasło! Spróbuj ponownie.")

    st.stop()


# --- RESZTA KODU (DOSTĘPNA TYLKO PO ZALOGOWANIU) ---

# Funkcja łącząca się z Arkuszami Google
def polacz_z_google_sheets():
    try:
        if "gcp_service_account" in st.secrets:
            dane_sekretow = st.secrets["gcp_service_account"]
            if isinstance(dane_sekretow, str):
                credentials_info = json.loads(dane_sekretow)
            else:
                credentials_info = dict(dane_sekretow)
            client = gspread.service_account_from_dict(credentials_info)
        else:
            client = gspread.service_account(filename="creds.json")

        plik_google = client.open("BUSYNDCBYDGOSZCZ")
        sheet = plik_google.worksheet("System_Kar_i_Kosztow")
        return sheet

    except Exception as e:
        st.error(f"❌ Błąd połączenia z Google Sheets: {e}")
        return None


def pobierz_dataframe(sheet):
    """Pobiera dane z Google Sheets i zwraca gotowy DataFrame."""
    try:
        dane = sheet.get_all_records()
        if not dane:
            return None

        df = pd.DataFrame(dane)

        # Dynamiczne wykrywanie nazw kolumn
        kolumna_koszt = next((c for c in df.columns if "Koszt" in c), None)
        kolumna_projekt = next((c for c in df.columns if "Projekt" in c or "projekt" in c), None)
        kolumna_typ = next((c for c in df.columns if "Typ" in c), None)
        kolumna_data = next((c for c in df.columns if "dzień" in c or "Data" in c or "data" in c), None)
        kolumna_imie = next((c for c in df.columns if "Imię" in c or "imie" in c.lower()), None)
        kolumna_nazwisko = next((c for c in df.columns if "Nazwisko" in c or "nazwisko" in c.lower()), None)

        # Zmień nazwy kolumn na ujednolicone
        rename_map = {}
        if kolumna_koszt:    rename_map[kolumna_koszt]    = "Koszt"
        if kolumna_projekt:  rename_map[kolumna_projekt]  = "Projekt"
        if kolumna_typ:      rename_map[kolumna_typ]      = "Typ"
        if kolumna_data:     rename_map[kolumna_data]     = "Data"
        if kolumna_imie:     rename_map[kolumna_imie]     = "Imie"
        if kolumna_nazwisko: rename_map[kolumna_nazwisko] = "Nazwisko"
        df = df.rename(columns=rename_map)

        df["Koszt"]       = pd.to_numeric(df["Koszt"], errors="coerce").fillna(0)
        df["Data"]        = pd.to_datetime(df["Data"], errors="coerce")
        df["Rok-Miesiac"] = df["Data"].dt.strftime("%Y-%m")

        if "Imie" in df.columns and "Nazwisko" in df.columns:
            df["Pracownik"] = df["Imie"].str.strip() + " " + df["Nazwisko"].str.strip()
        elif "Imie" in df.columns:
            df["Pracownik"] = df["Imie"].str.strip()
        else:
            df["Pracownik"] = "Nieznany"

        return df
    except Exception as e:
        st.error(f"❌ Błąd podczas pobierania danych: {e}")
        return None


# -------------------------------------------------------
# 🤖  AI – Raport miesięczny
# -------------------------------------------------------
def generuj_raport_ai(df, wybrany_miesiac):
    """Wysyła dane do Claude API i zwraca raport tekstowy."""
    try:
        client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    except Exception:
        st.error("❌ Brak klucza ANTHROPIC_API_KEY w st.secrets. Dodaj go w ustawieniach Streamlit.")
        return None

    df_m = df[df["Rok-Miesiac"] == wybrany_miesiac] if wybrany_miesiac != "Wszystkie" else df

    if df_m.empty:
        st.warning("Brak danych dla wybranego okresu.")
        return None

    suma_kar    = df_m[df_m["Typ"] == "Kara"]["Koszt"].sum()
    suma_doplat = df_m[df_m["Typ"] == "Dopłata"]["Koszt"].sum()
    liczba_wpisow = len(df_m)

    ranking_pracownikow = (
        df_m.groupby("Pracownik")["Koszt"].sum()
        .sort_values(ascending=False)
        .head(5)
        .to_dict()
    )

    koszty_projektow = (
        df_m.groupby("Projekt")["Koszt"].sum()
        .sort_values(ascending=False)
        .to_dict()
    )

    prompt = f"""
Jesteś analitykiem kosztów w firmie logistycznej. Na podstawie poniższych danych wygeneruj profesjonalne 
podsumowanie miesiąca w języku polskim. Pisz rzeczowo, zwięźle, w punktach. Wskaż najważniejsze obserwacje,
zagrożenia oraz zalecenia działań naprawczych.

DANE ZA OKRES: {wybrany_miesiac}
- Łączna suma kar: {suma_kar:.2f} zł
- Łączna suma dopłat: {suma_doplat:.2f} zł
- Łączna liczba wpisów: {liczba_wpisow}

TOP 5 PRACOWNIKÓW WG KOSZTÓW:
{json.dumps(ranking_pracownikow, ensure_ascii=False, indent=2)}

KOSZTY WG PROJEKTÓW:
{json.dumps(koszty_projektow, ensure_ascii=False, indent=2)}

Wygeneruj raport w sekcjach:
1. 📌 Podsumowanie ogólne
2. ⚠️ Kluczowe obserwacje i ryzyka
3. 🏆 Pracownicy wymagający uwagi (wymień z konkretnymi kwotami)
4. ✅ Zalecenia i działania naprawcze
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text
    except Exception as e:
        st.error(f"❌ Błąd API Claude: {e}")
        return None


# -------------------------------------------------------
# 📈  Predykcja kosztów
# -------------------------------------------------------
def predykcja_kosztow(df):
    """Prognozuje koszty na następny miesiąc metodą regresji liniowej."""
    miesieczne = (
        df.groupby("Rok-Miesiac")["Koszt"]
        .sum()
        .reset_index()
        .sort_values("Rok-Miesiac")
    )

    if len(miesieczne) < 3:
        st.info("ℹ️ Potrzeba co najmniej 3 miesięcy danych, aby wykonać predykcję.")
        return

    miesieczne["Index"] = range(len(miesieczne))
    X = miesieczne[["Index"]].values
    y = miesieczne["Koszt"].values

    model = LinearRegression()
    model.fit(X, y)

    nastepny_index = np.array([[len(miesieczne)]])
    prognoza = model.predict(nastepny_index)[0]

    # Nazwa następnego miesiąca
    ostatni_miesiac = pd.to_datetime(miesieczne["Rok-Miesiac"].iloc[-1] + "-01")
    nastepny_miesiac = (ostatni_miesiac + pd.DateOffset(months=1)).strftime("%Y-%m")

    st.subheader("📈 Predykcja kosztów")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Poprzedni miesiąc", f"{y[-2]:.0f} zł" if len(y) >= 2 else "—")
    with col_b:
        st.metric("Ostatni miesiąc", f"{y[-1]:.0f} zł")
    with col_c:
        delta = prognoza - y[-1]
        st.metric(
            f"Prognoza {nastepny_miesiac}",
            f"{max(prognoza, 0):.0f} zł",
            delta=f"{delta:+.0f} zł",
            delta_color="inverse"
        )

    st.write("📊 **Trend miesięczny:**")
    chart_data = pd.DataFrame({
        "Miesiąc":     list(miesieczne["Rok-Miesiac"]) + [nastepny_miesiac],
        "Koszt (zł)":  list(y) + [max(prognoza, 0)],
        "Typ":         ["Historia"] * len(y) + ["Prognoza"]
    }).set_index("Miesiąc")
    st.line_chart(chart_data[["Koszt (zł)"]])
    st.caption("Prognoza oparta na regresji liniowej z danych historycznych.")


# ============================================================
# GŁÓWNY INTERFEJS
# ============================================================
sheet = polacz_z_google_sheets()

col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title("🚨 System Rejestracji Kosztów")
with col_logout:
    st.write("")
    if st.button("🔒 Wyloguj"):
        st.session_state["zalogowano"] = False
        st.rerun()

st.write("Każdy wpis zostanie natychmiast zapisany w chmurze i zsynchronizowany na wszystkich urządzeniach.")

# --- FORMULARZ WPISYWANIA DANYCH ---
with st.form("formularz_kosztow", clear_on_submit=True):
    st.subheader("📝 Nowe zgłoszenie")

    data_dotyczy = st.date_input("Za jaki dzień jest kara / dopłata?", value=datetime.now())

    col1, col2 = st.columns(2)
    with col1:
        imie = st.text_input("Imię").strip()
    with col2:
        nazwisko = st.text_input("Nazwisko").strip()

    projekt_wybor = st.selectbox(
        "Wybierz Projekt",
        ["Auchan", "Orlen Paczka", "Agata Meble", "Inny (Wpisz ręcznie)"]
    )

    projekt_reczny = ""
    if projekt_wybor == "Inny (Wpisz ręcznie)":
        projekt_reczny = st.text_input("Wpisz nazwę nowego projektu").strip()

    typ_wpisu = st.selectbox("Typ wpisu", ["Dopłata", "Kara"])
    koszt     = st.number_input("Koszt całkowity (zł)", min_value=0.0, step=10.0, value=0.0)
    uwagi     = st.text_area("Uwagi / Powód")

    submit_button = st.form_submit_button("ZAPISZ W CHMURZE")

# --- LOGIKA ZAPISU ---
if submit_button:
    ostateczny_projekt = projekt_reczny if projekt_wybor == "Inny (Wpisz ręcznie)" else projekt_wybor

    if not imie or not nazwisko or not ostateczny_projekt or koszt == 0:
        st.error("❌ Błąd! Pola Imię, Nazwisko, Projekt oraz Koszt nie mogą być puste.")
    elif sheet is None:
        st.error("❌ Brak połączenia z bazą danych.")
    else:
        zeit_now  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_str  = data_dotyczy.strftime("%Y-%m-%d")
        powod_uwagi = uwagi if uwagi else "Brak uwag"

        nowy_wiersz = [zeit_now, data_str, imie, nazwisko, ostateczny_projekt, typ_wpisu, koszt, powod_uwagi]

        try:
            sheet.append_row(nowy_wiersz)
            st.success(f"✅ Zapisano w chmurze Google! (Projekt: {ostateczny_projekt}, Dzień: {data_str})")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Błąd podczas zapisu danych: {e}")

# ============================================================
# SEKCJE ANALITYCZNE
# ============================================================
st.write("---")

if sheet is not None:
    df = pobierz_dataframe(sheet)

    if df is not None and not df.empty:

        # -------------------------------------------------------
        # 🏆  RANKING PRACOWNIKÓW
        # -------------------------------------------------------
        st.subheader("🏆 Ranking pracowników wg kosztów")

        miesiace_dostepne = ["Wszystkie"] + sorted(df["Rok-Miesiac"].dropna().unique().tolist(), reverse=True)
        wybrany_miesiac_ranking = st.selectbox("📅 Okres rankingu", miesiace_dostepne, key="ranking_miesiac")

        df_rank = df if wybrany_miesiac_ranking == "Wszystkie" else df[df["Rok-Miesiac"] == wybrany_miesiac_ranking]

        if not df_rank.empty:
            ranking = (
                df_rank.groupby("Pracownik")["Koszt"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            ranking.index += 1
            ranking.columns = ["Pracownik", "Łączny koszt (zł)"]
            ranking["Łączny koszt (zł)"] = ranking["Łączny koszt (zł)"].map(lambda x: f"{x:.2f} zł")

            # Medale dla top 3
            def medal(i):
                return {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")

            ranking.index = [medal(i) for i in range(1, len(ranking) + 1)]
            st.dataframe(ranking, use_container_width=True)
        else:
            st.info("Brak danych dla wybranego okresu.")

        # -------------------------------------------------------
        # 🤖  RAPORT AI
        # -------------------------------------------------------
        st.write("---")
        st.subheader("🤖 Raport AI – podsumowanie miesięczne")

        miesiace_ai = ["Wszystkie"] + sorted(df["Rok-Miesiac"].dropna().unique().tolist(), reverse=True)
        wybrany_miesiac_ai = st.selectbox("📅 Okres raportu", miesiace_ai, key="ai_miesiac")

        if st.button("✨ Generuj raport AI", type="primary"):
            with st.spinner("🤖 Claude analizuje dane... To może chwilę potrwać."):
                raport = generuj_raport_ai(df, wybrany_miesiac_ai)
            if raport:
                st.success("Raport wygenerowany!")
                st.markdown(raport)

        # -------------------------------------------------------
        # 📈  PREDYKCJA KOSZTÓW
        # -------------------------------------------------------
        st.write("---")
        predykcja_kosztow(df)

        # -------------------------------------------------------
        # 📋  OSTATNIE WPISY
        # -------------------------------------------------------
        st.write("---")
        st.subheader("📋 Ostatnie 10 wpisów w bazie")
        st.dataframe(df.tail(10), use_container_width=True)

    else:
        st.info("Baza jest pusta. Dodaj pierwszy wpis przez formularz powyżej!")
