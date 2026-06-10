import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime

# Konfiguracja strony
st.set_page_config(page_title="System Alertów i Kosztów CHMURA", page_icon="🚨", layout="centered")

# ==========================================
# 🔑 KONFIGURACJA HASŁA DOSTĘPU
# Możesz zmienić tekst w cudzysłowie na swoje własne hasło
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
            
    # Zatrzymujemy działanie reszty programu, jeśli użytkownik nie jest zalogowany
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

sheet = polacz_z_google_sheets()

# Przycisk do wylogowania na samej górze panelu głównego
col_title, col_logout = st.columns([4, 1])
with col_title:
    st.title("🚨 System Rejestracji Kosztów")
with col_logout:
    st.write("") # mały odstęp pionowy
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
    
    typ_wpisu = st.selectbox(
        "Typ wpisu", 
        ["Dopłata", "Kara"]
    )
    
    koszt = st.number_input("Koszt całkowity (zł)", min_value=0.0, step=10.0, value=0.0)
    uwagi = st.text_area("Uwagi / Powód")

    submit_button = st.form_submit_button("ZAPISZ W CHMURZE")

# --- LOGIKA ZAPISU ---
if submit_button:
    ostateczny_projekt = projekt_reczny if projekt_wybor == "Inny (Wpisz ręcznie)" else projekt_wybor

    if not imie or not nazwisko or not ostateczny_projekt or koszt == 0:
        st.error("❌ Błąd! Pola Imię, Nazwisko, Projekt oraz Koszt nie mogą być puste.")
    elif sheet is None:
        st.error("❌ Brak połączenia z bazą danych.")
    else:
        zeit_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_str = data_dotyczy.strftime("%Y-%m-%d")
        powod_uwagi = uwagi if uwagi else "Brak uwag"
        
        nowy_wiersz = [zeit_now, data_str, imie, nazwisko, ostateczny_projekt, typ_wpisu, koszt, powod_uwagi]
        
        try:
            sheet.append_row(nowy_wiersz)
            st.success(f"✅ Zapisano w chmurze Google! (Projekt: {ostateczny_projekt}, Dzień: {data_str})")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Błąd podczas zapisu danych: {e}")

# --- POBIERANIE I ANALIZA DANYCH ---
st.write("---")
if sheet is not None:
    try:
        dane_z_chmury = sheet.get_all_records()
        
        if dane_z_chmury:
            df = pd.DataFrame(dane_z_chmury)
            
            # --- SEKCJA 1: SUMOWANIE DLA PROJEKTÓW ---
            st.subheader("📊 Podsumowanie Finansowe Projektów")
            
            kolumna_koszt = "Koszt całkowity (zł)" 
            kolumna_projekt = "Nazwa Projektu (np. Auchan)"
            kolumna_typ = "Typ wpisu"
            
            if "Nazwa Projektu" in df.columns: kolumna_projekt = "Nazwa Projektu"
            elif "Projekt" in df.columns: kolumna_projekt = "Projekt"
            elif "Nazwa Projektu (np. Auchan)" in df.columns: kolumna_projekt = "Nazwa Projektu (np. Auchan)"
                
            if "Koszt" in df.columns: kolumna_koszt = "Koszt"
            elif "Koszt całkowity" in df.columns: kolumna_koszt = "Koszt całkowity"
            elif "Koszt całkowity (zł)" in df.columns: kolumna_koszt = "Koszt całkowity (zł)"
                
            if "Typ" in df.columns: kolumna_typ = "Typ"
            elif "Typ wpisu" in df.columns: kolumna_typ = "Typ wpisu"

            df[kolumna_koszt] = pd.to_numeric(df[kolumna_koszt], errors='coerce').fillna(0)
            
            tabela_podsumowania = df.groupby([kolumna_projekt, kolumna_typ])[kolumna_koszt].sum().unstack(fill_value=0)
            
            if "Kara" not in tabela_podsumowania.columns:
                tabela_podsumowania["Kara"] = 0.0
            if "Dopłata" not in tabela_podsumowania.columns:
                tabela_podsumowania["Dopłata"] = 0.0
                
            tabela_podsumowania = tabela_podsumowania[["Kara", "Dopłata"]]
            tabela_podsumowania["Suma Łączna (zł)"] = tabela_podsumowania["Kara"] + tabela_podsumowania["Dopłata"]
            
            st.dataframe(tabela_podsumowania.style.format("{:.2f} zł"), use_container_width=True)
            
            # --- SEKCJA 2: OSTATNIE WPISY ---
            st.write("---")
            st.subheader("📋 Ostatnie 10 wpisów w bazie")
            st.dataframe(df.tail(10), use_container_width=True)
            
        else:
            st.info("Ta zakładka jest obecnie pusta w Google Sheets. Dodaj pierwszy wpis przez formularz powyżej!")
            
    except Exception as e:
        st.warning("Tabela podsumowania za chwilę wyliczy się automatycznie.")