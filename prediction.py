import streamlit as st
import numpy as np
import pickle
import pandas as pd
import tensorflow as tf
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Load model dan scaler
DO_model = tf.keras.models.load_model('best_lstm_model6.h5')
scaler = pickle.load(open('Scaler6.pkl', 'rb'))

# Database connection setup
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
engine = create_engine(DATABASE_URL)

# Definisi fitur untuk preprocessing
IPS_COLUMNS = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
ADDITIONAL_COLUMNS = ['SKS7', 'IPKS7']
PRODI_COLUMNS = ['Prodi_31201', 'Prodi_33201', 'Prodi_34201', 'Prodi_38201', 'Prodi_44201', 
                 'Prodi_45201', 'Prodi_46201', 'Prodi_47201', 'Prodi_49201', 'Prodi_51201', 
                 'Prodi_54207', 'Prodi_59202']
JALUR_MASUK_COLUMNS = ['Jalur_12.0', 'Jalur_14.0', 'Jalur_15.0', 'Jalur_Unknown']

# Program studi and jalur masuk definitions
PROGRAM_STUDI_OPTIONS = {
    '31201': 'Teknik Pertambangan',
    '33201': 'Teknik Geofisika',
    '34201': 'Teknik Geologi',
    '38201': 'Oseanografi',
    '44201': 'Matematika',
    '45201': 'Fisika',
    '46201': 'Biologi',
    '47201': 'Kimia',
    '49201': 'Statistika',
    '51201': 'Geografi',
    '54207': 'Bioteknologi',
    '59202': 'Ilmu Komputer'
}

JALUR_MASUK_OPTIONS = {
    '12': 'Seleksi Mandiri',
    '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
    '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)',
    'Unknown': 'Tidak Diketahui'
}

def preprocess_input_data(data_uji):
    # Ensure data_uji is a DataFrame
    if not isinstance(data_uji, pd.DataFrame):
        data_uji = pd.DataFrame(data_uji)
    
    # Columns to convert to numeric
    numeric_columns = IPS_COLUMNS + ADDITIONAL_COLUMNS

    # Convert all numeric columns to float, replacing non-numeric values
    for col in numeric_columns:
        # Replace problematic values
        data_uji[col] = data_uji[col].replace(['', ' ', 'NA', 'NaN', 'null'], np.nan)
        
        # Attempt to convert to numeric, coercing errors to NaN
        data_uji[col] = pd.to_numeric(data_uji[col], errors='coerce')
    
    # Fill NaN values with 0 or method appropriate for your data
    data_uji[numeric_columns] = data_uji[numeric_columns].fillna(0)

    # Handle categorical columns
    # Ensure Program Studi is converted to string and mapped to known codes
    if 'Program Studi' in data_uji.columns:
        # Convert to string and map to known codes
        data_uji['Program Studi'] = data_uji['Program Studi'].astype(str).map(
            {v: k for k, v in PROGRAM_STUDI_OPTIONS.items()}
        ).fillna(list(PROGRAM_STUDI_OPTIONS.keys())[0])  # Default to first known code if not found

    # Similar handling for Jalur Masuk
    if 'Jalur Masuk' in data_uji.columns:
        data_uji['Jalur Masuk'] = data_uji['Jalur Masuk'].astype(str).map(
            {v: k for k, v in JALUR_MASUK_OPTIONS.items()}
        ).fillna('Unknown')

    # One-hot encoding for Program Studi
    prodi_encoded = pd.get_dummies(data_uji['Program Studi'], prefix='Prodi')
    for col in PRODI_COLUMNS:
        if col not in prodi_encoded.columns:
            prodi_encoded[col] = 0
    prodi_encoded = prodi_encoded[PRODI_COLUMNS]

    # One-hot encoding for Jalur Masuk
    jalur_masuk_encoded = pd.get_dummies(data_uji['Jalur Masuk'], prefix='Jalur')
    for col in JALUR_MASUK_COLUMNS:
        if col not in jalur_masuk_encoded.columns:
            jalur_masuk_encoded[col] = 0
    jalur_masuk_encoded = jalur_masuk_encoded[JALUR_MASUK_COLUMNS]

    # Combine all features
    combined_features = pd.concat([
        data_uji[numeric_columns], 
        prodi_encoded, 
        jalur_masuk_encoded
    ], axis=1)

    # Ensure all columns are float
    combined_features = combined_features.astype(float)

    # Skalakan fitur
    X_uji_scaled = scaler.transform(combined_features.values)

    # Reshape untuk LSTM
    X_uji_reshaped = X_uji_scaled.reshape((X_uji_scaled.shape[0], 1, X_uji_scaled.shape[1]))

    return X_uji_reshaped

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    try:
        with engine.connect() as connection:
            current_admin_id = st.session_state.get('user_id', 1)
            
            mahasiswa_check_query = text("""
                SELECT id_mahasiswa 
                FROM `mahasiswa` 
                WHERE NIM = :nim
            """)
            mahasiswa_result = connection.execute(mahasiswa_check_query, {"nim": nim}).fetchone()

            if not mahasiswa_result:
                mahasiswa_query = text("""
                    INSERT INTO `mahasiswa` 
                    (nama, NIM, `angkatan`, `program_studi`, `jalur_masuk`)
                    VALUES (:nama, :nim, :angkatan, :program_studi, :jalur_masuk)
                """)
                connection.execute(mahasiswa_query, {
                    "nama": nama, 
                    "nim": nim, 
                    "angkatan": angkatan, 
                    "jalur_masuk": jalur_masuk,
                    "program_studi": program_studi
                })
                mahasiswa_result = connection.execute(mahasiswa_check_query, {"nim": nim}).fetchone()

            id_mahasiswa = mahasiswa_result[0]

            prediksi_query = text("""
                INSERT INTO `prediksi` 
                (id_mahasiswa, id_user, tanggal_prediksi, hasil_klasifikasi, probabilitas)
                VALUES (:id_mahasiswa, :id_user, CURDATE(), :hasil, :probabilitas)
            """)
            connection.execute(prediksi_query, {
                "id_mahasiswa": id_mahasiswa,
                "id_user": current_admin_id,
                "hasil": hasil,
                "probabilitas": probabilitas
            })

            riwayat_check_query = text("""
                SELECT COUNT(*) 
                FROM `riwayat_akademik` 
                WHERE id_mahasiswa = :id_mahasiswa
            """)
            riwayat_result = connection.execute(riwayat_check_query, {"id_mahasiswa": id_mahasiswa}).fetchone()

            if riwayat_result[0] == 0:
                riwayat_query = text("""
                    INSERT INTO `riwayat_akademik` 
                    (id_mahasiswa, ips_1, ips_2, ips_3, ips_4, ips_5, ips_6, ips_7, ipks_7, sks_7)
                    VALUES (:id_mahasiswa, :ips_1, :ips_2, :ips_3, :ips_4, :ips_5, :ips_6, :ips_7, :ipks_7, :sks_7)
                """)
                connection.execute(riwayat_query, {
                    "id_mahasiswa": id_mahasiswa,
                    "ips_1": academic_data[2],  # IPS1
                    "ips_2": academic_data[3],  # IPS2
                    "ips_3": academic_data[4],  # IPS3
                    "ips_4": academic_data[5],  # IPS4
                    "ips_5": academic_data[6],  # IPS5
                    "ips_6": academic_data[7],  # IPS6
                    "ips_7": academic_data[8],  # IPS7
                    "ipks_7": academic_data[1], # IPKS7
                    "sks_7": academic_data[0]   # SKS7
                })

            connection.commit()
            return True, "Data berhasil disimpan"
    
    except Exception as e:
        return False, f"Error: {str(e)}"

def run_prediction():
    st.title('Klasifikasi Mahasiswa Berpotensi DO')

    tab1, tab2 = st.tabs(["Klasifikasi Manual", "Unggah File"])

    with tab1:
        # Input manual
        nama = st.text_input('Nama')
        nim = st.text_input('NIM')
        angkatan = st.text_input('Angkatan')
        
        program_studi_code = st.selectbox('Program Studi', options=list(PROGRAM_STUDI_OPTIONS.keys()), format_func=lambda x: f"{x} - {PROGRAM_STUDI_OPTIONS[x]}")
        program_studi = program_studi_code
        
        jalur_masuk_code = st.selectbox('Jalur Masuk', options=list(JALUR_MASUK_OPTIONS.keys()), format_func=lambda x: f"{x} - {JALUR_MASUK_OPTIONS[x]}")
        jalur_masuk = jalur_masuk_code
    
        # Input data akademik
        SKS7 = st.text_input('Total SKS Semester 7')
        IPKS7 = st.text_input('Indeks Prestasi Kumulatif Semester 7 (IPKS7)')
        IPS1 = st.text_input('Indeks Prestasi Semester 1 (IPS1)')
        IPS2 = st.text_input('Indeks Prestasi Semester 2 (IPS2)')
        IPS3 = st.text_input('Indeks Prestasi Semester 3 (IPS3)')
        IPS4 = st.text_input('Indeks Prestasi Semester 4 (IPS4)')
        IPS5 = st.text_input('Indeks Prestasi Semester 5 (IPS5)')
        IPS6 = st.text_input('Indeks Prestasi Semester 6 (IPS6)')
        IPS7 = st.text_input('Indeks Prestasi Semester 7 (IPS7)')

        if st.button('Klasifikasi Status Mahasiswa'):
            try:
                # Prepare data for prediction
                data_uji = pd.DataFrame({
                    'SKS7': [float(SKS7)],
                    'IPKS7': [float(IPKS7)],
                    'IPS1': [float(IPS1)],
                    'IPS2': [float(IPS2)],
                    'IPS3': [float(IPS3)],
                    'IPS4': [float(IPS4)],
                    'IPS5': [float(IPS5)],
                    'IPS6': [float(IPS6)],
                    'IPS7': [float(IPS7)],
                    'Program Studi': [program_studi_code],
                    'Jalur Masuk': [jalur_masuk_code]
                })

                # Preprocessing
                input_sequence = preprocess_input_data(data_uji)

                # Predict
                DO_predik = DO_model.predict(input_sequence)[0][0]

                # Determine prediction result
                hasil = 'Berpotensi DO' if DO_predik >= 0.5 else 'Tidak Berpotensi DO'

                # Display the result
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi_code} - {PROGRAM_STUDI_OPTIONS[program_studi_code]}")
                st.write(f"Jalur Masuk: {jalur_masuk_code} - {JALUR_MASUK_OPTIONS[jalur_masuk_code]}")
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {DO_predik:.2f}")

                # Save to database
                numerical_data = [
                    float(SKS7), float(IPKS7), float(IPS1), float(IPS2), float(IPS3),
                    float(IPS4), float(IPS5), float(IPS6), float(IPS7)
                ]
                success, message = save_prediction_to_db(
                    engine, nama, nim, angkatan, jalur_masuk, program_studi,
                    hasil, DO_predik, numerical_data
                )
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")
    
    with tab2:
        # Upload file prediksi
        uploaded_file = st.file_uploader("Klasifikasi dari File (CSV atau Excel)", type=['csv', 'xlsx', 'xls'])

        if uploaded_file is not None:
            try:
                # Load file
                if uploaded_file.name.endswith('.csv'):
                    data_uji = pd.read_csv(uploaded_file)
                else:
                    data_uji = pd.read_excel(uploaded_file)

                # Definisikan kolom yang dibutuhkan
                required_columns = ['Nama', 'NIM', 'Angkatan', 'Program Studi', 'Jalur Masuk', 
                                    'SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                
                # Validasi kolom
                for col in required_columns:
                    if col not in data_uji.columns:
                        st.error(f"Kolom {col} tidak ditemukan dalam file!")
                        st.stop()

                # Preprocessing
                X_uji_reshaped = preprocess_input_data(data_uji)

                # Predict
                predictions_prob = DO_model.predict(X_uji_reshaped).flatten()  # Flatten the predictions

                # Menggabungkan hasil prediksi dengan data asli
                data_uji['Probabilitas'] = predictions_prob
                data_uji['Prediksi_Status'] = [
                    'Berpotensi DO' if prob >= 0.5 else 'Tidak Berpotensi DO' 
                    for prob in predictions_prob
                ]

                # Tampilkan hasil
                st.write("Hasil Klasifikasi:", data_uji)

                # Simpan prediksi ke database
                total_mahasiswa = len(data_uji)
                berhasil_disimpan = 0
                gagal_disimpan = 0

                with engine.connect() as connection:
                    for _, row in data_uji.iterrows():
                        academic_data = [
                            row['SKS7'], row['IPKS7'], row['IPS1'], row['IPS2'], row['IPS3'], 
                            row['IPS4'], row['IPS5'], row['IPS6'], row['IPS7']
                        ]
                        
                        # Simpan prediksi
                        success, message = save_prediction_to_db(
                            engine,
                            row['Nama'], 
                            row['NIM'], 
                            str(row['Angkatan']), 
                            str(row['Jalur Masuk']), 
                            str(row['Program Studi']),
                            row['Prediksi_Status'], 
                            float(row['Probabilitas']),
                            academic_data
                        )
                        if success:
                            berhasil_disimpan += 1
                        else:
                            gagal_disimpan += 1

                # Tampilkan ringkasan
                if gagal_disimpan > 0:
                    st.warning(f"Dataset sebagian gagal disimpan, dari total {total_mahasiswa} mahasiswa, {berhasil_disimpan} berhasil disimpan dan {gagal_disimpan} gagal disimpan.")
                else:
                    st.success(f"Semua {total_mahasiswa} mahasiswa berhasil disimpan.")

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")

if __name__ == "__main__":
    run_prediction()