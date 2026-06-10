import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import json

# Konfiguracja strony
st.set_page_config(page_title="System Alertów i Kosztów CHMURA", page_icon="🚨", layout="centered")

# Funkcja łącząca się z Arkuszami Google
def polacz_z_google_sheets():
    try:
        # SPRAWDZAMY CZY JESTEŚMY W CHMURZE STREAMLIT
        if "gcp_service_account" in st.secrets:
            credentials_info = json.loads(st.secrets["gcp_service_account"])
            client = gspread.service_account_from_dict(credentials_info)
        else:
            # LOKALNIE NA KOMPUTERZE (Z start.bat)
            client = gspread.service_account(filename="creds.json")
        
        # Otwieramy główny plik za pomocą jego nazwy
        plik_google = client.open("BUSYNDCBYDGOSZCZ")
        
        # Wskazujemy konkretną zakładkę
        sheet = plik_google.worksheet("System_Kar_i_Kosztow")
        return sheet
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error("❌ Nie znaleziono pliku o nazwie 'BUSYNDCBYDGOSZCZ'. Sprawdź, czy na pewno udostępniłeś ten główny plik mailowi z pliku creds.json!")
        return None
    except gspread.exceptions.WorksheetNotFound:
        st.error("❌ W pliku znaleziono połączenie, ale nie ma w nim zakładki o nazwie 'System_Kar_i_Kosztow'. Sprawdź, czy nie ma tam ukrytej spacji!")
        return None
    except Exception as e:
        st.error(f"❌ Błąd połączenia z Google Sheets: {e}")
        return None

sheet = polacz_z_google_sheets()

st.title("🚨 System Rejestracji Kosztów (Chmura Google)")
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
        
    projekt = st.text_input("Nazwa Projektu (np. Auchan)").strip()
    
    typ_wpisu = st.selectbox(
        "Typ wpisu", 
        ["Dopłata", "Kara"]
    )
    
    koszt = st.number_input("Koszt całkowity (zł)", min_value=0.0, step=10.0, value=0.0)
    uwagi = st.text_area("Uwagi / Powód")

    submit_button = st.form_submit_button("ZAPISZ W CHMURZE")

# --- LOGIKA ZAPISU ---
if submit_button:
    if not imie or not nazwisko or not projekt or koszt == 0:
        st.error("❌ Błąd! Pola Imię, Nazwisko, Projekt oraz Koszt nie mogą być puste.")
    elif sheet is None:
        st.error("❌ Brak połączenia z bazą danych.")
    else:
        zeit_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data_str = data_dotyczy.strftime("%Y-%m-%d")
        powod_uwagi = uwagi if uwagi else "Brak uwag"
        
        nowy_wiersz = [zeit_now, data_str, imie, nazwisko, projekt, typ_wpisu, koszt, powod_uwagi]
        
        try:
            sheet.append_row(nowy_wiersz)
            st.success(f"✅ Zapisano w chmurze Google! (Dzień: {data_str})")
            st.balloons()
        except Exception as e:
            st.error(f"❌ Błąd podczas zapisu danych: {e}")

# --- PODGLĄD NA ŻYWO Z CHMURY ---
st.write("---")
st.subheader("📊 Podgląd bazy danych w chmurze na żywo")
if sheet is not None:
    try:
        dane_z_chmury = sheet.get_all_records()
        if dane_z_chmury:
            df_podglad = pd.DataFrame(dane_z_chmury)
            st.dataframe(df_podglad.tail(10), use_container_width=True)
        else:
            st.info("Ta zakładka jest obecnie pusta w Google Sheets. Dodaj pierwszy wpis przez formularz powyżej!")
    except Exception as e:
        st.warning("Tabela za chwilę załaduje się poprawnie (kliknij F5 jeśli podgląd nie wskoczył).")