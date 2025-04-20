import streamlit as st
import numpy as np
import pickle
import pandas as pd
import tensorflow as tf
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# model prediksi
DO_model = tf.keras.models.load_model('best_lstm_model10.h5')
scaler = pickle.load(open('Scaler10.pkl', 'rb'))

# koneksi database
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
engine = create_engine(DATABASE_URL)

# Definisi fitur untuk preprocessing
IPS_COLUMNS = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
ADDITIONAL_COLUMNS = ['SKS7', 'IPKS7']
PRODI_COLUMNS = ['Prodi_31201', 'Prodi_33201', 'Prodi_34201', 'Prodi_38201', 'Prodi_44201', 
                 'Prodi_45201', 'Prodi_46201', 'Prodi_47201', 'Prodi_49201', 'Prodi_51201', 
                 'Prodi_54207', 'Prodi_59202']
JALUR_MASUK_COLUMNS = ['Jalur_12', 'Jalur_14', 'Jalur_15', 'Jalur_Unknown']

# Program studi and jalur masuk
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
    if not isinstance(data_uji, pd.DataFrame):
        data_uji = pd.DataFrame(data_uji)
    
    # kolom yg mau diconvert ke numerik
    numeric_columns = IPS_COLUMNS + ADDITIONAL_COLUMNS

    for col in numeric_columns:
        data_uji[col] = data_uji[col].replace(['', ' ', 'NA', 'NaN', 'null'], np.nan)

        data_uji[col] = pd.to_numeric(data_uji[col], errors='coerce')
    
    data_uji[numeric_columns] = data_uji[numeric_columns].fillna(0)

    # kategorikal kolom
    if 'Program Studi' in data_uji.columns:
        #program studi
        data_uji['Program Studi'] = data_uji['Program Studi'].astype(str)
        valid_prodi_codes = list(PROGRAM_STUDI_OPTIONS.keys())
        data_uji['Program Studi'] = data_uji['Program Studi'].apply(
            lambda x: x if x in valid_prodi_codes else valid_prodi_codes[0]
        )

    # jalur masuk
    if 'Jalur Masuk' in data_uji.columns:
        data_uji['Jalur Masuk'] = data_uji['Jalur Masuk'].astype(str).apply(
            lambda x: x.split('.')[0] if '.' in x else x
        )

        data_uji['Jalur Masuk'] = data_uji['Jalur Masuk'].apply(
            lambda x: x if x in JALUR_MASUK_OPTIONS.keys() else 'Unknown'
        )
    
    # One-hot encoding untuk Program Studi
    prodi_encoded = pd.get_dummies(data_uji['Program Studi'], prefix='Prodi')
    for col in PRODI_COLUMNS:
        if col not in prodi_encoded.columns:
            prodi_encoded[col] = 0
    prodi_encoded = prodi_encoded[PRODI_COLUMNS]

    # One-hot encoding untuk Jalur Masuk
    jalur_masuk_encoded = pd.get_dummies(data_uji['Jalur Masuk'], prefix='Jalur')
    
    for col in JALUR_MASUK_COLUMNS:
        if col not in jalur_masuk_encoded.columns:
            jalur_masuk_encoded[col] = 0
    
    jalur_masuk_encoded = jalur_masuk_encoded[JALUR_MASUK_COLUMNS]

    #mengcombine semua fitur
    combined_features = pd.concat([
        data_uji[numeric_columns], 
        prodi_encoded, 
        jalur_masuk_encoded
    ], axis=1)

    #pastikan semuanya float
    combined_features = combined_features.astype(float)

    # normalisasi data
    X_uji_scaled = scaler.transform(combined_features.values)

    # Reshape untuk LSTM
    X_uji_reshaped = X_uji_scaled.reshape((X_uji_scaled.shape[0], 1, X_uji_scaled.shape[1]))

    return X_uji_reshaped

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    try:
        if program_studi not in PROGRAM_STUDI_OPTIONS:
            program_studi = list(PROGRAM_STUDI_OPTIONS.keys())[0]
        
        if jalur_masuk and '.' in jalur_masuk:
            jalur_masuk = jalur_masuk.split('.')[0]
            
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
                    "ips_1": academic_data[2],  
                    "ips_2": academic_data[3],  
                    "ips_3": academic_data[4],  
                    "ips_4": academic_data[5],  
                    "ips_5": academic_data[6],  
                    "ips_6": academic_data[7],  
                    "ips_7": academic_data[8],  
                    "ipks_7": academic_data[1], 
                    "sks_7": academic_data[0]   
                })

            connection.commit()
            return True, "Data berhasil disimpan"
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        st.error(f"Detail error: {error_details}")
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
                # Validasi jalur masuk
                if not jalur_masuk:
                    jalur_masuk = 'Unknown' 
                
                if '.' in jalur_masuk:
                    jalur_masuk = jalur_masuk.split('.')[0]
                    
                # menyiapkan data untuk prediksi
                data_uji = pd.DataFrame({
                    'SKS7': [float(SKS7) if SKS7 else 0],
                    'IPKS7': [float(IPKS7) if IPKS7 else 0],
                    'IPS1': [float(IPS1) if IPS1 else 0],
                    'IPS2': [float(IPS2) if IPS2 else 0],
                    'IPS3': [float(IPS3) if IPS3 else 0],
                    'IPS4': [float(IPS4) if IPS4 else 0],
                    'IPS5': [float(IPS5) if IPS5 else 0],
                    'IPS6': [float(IPS6) if IPS6 else 0],
                    'IPS7': [float(IPS7) if IPS7 else 0],
                    'Program Studi': [program_studi_code],
                    'Jalur Masuk': [jalur_masuk]
                })

                # Preprocessing
                input_sequence = preprocess_input_data(data_uji)

                # Prediksi
                DO_predik = DO_model.predict(input_sequence)[0][0]

                # menentukan hasil prediksi
                hasil = 'Berpotensi DO' if DO_predik >= 0.5 else 'Tidak Berpotensi DO'

                # menampilkan hasil
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi_code} - {PROGRAM_STUDI_OPTIONS[program_studi_code]}")
                
                jalur_display = f"{jalur_masuk} - {JALUR_MASUK_OPTIONS.get(jalur_masuk, 'Kode Kustom')}"
                st.write(f"Jalur Masuk: {jalur_display}")
                
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {DO_predik:.2f}")

                # Save ke database
                numerical_data = [
                    float(SKS7) if SKS7 else 0, 
                    float(IPKS7) if IPKS7 else 0,
                    float(IPS1) if IPS1 else 0,
                    float(IPS2) if IPS2 else 0,
                    float(IPS3) if IPS3 else 0,
                    float(IPS4) if IPS4 else 0,
                    float(IPS5) if IPS5 else 0,
                    float(IPS6) if IPS6 else 0,
                    float(IPS7) if IPS7 else 0
                ]
                
                success, message = save_prediction_to_db(
                    engine, nama, nim, str(angkatan), jalur_masuk, program_studi,
                    hasil, DO_predik, numerical_data
                )
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                st.error(f"Terjadi kesalahan: {str(e)}")
                st.error(f"Detail error: {error_details}")
    
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

                data_uji['NIM'] = data_uji['NIM'].astype(str)
                
                data_uji['Program Studi'] = data_uji['Program Studi'].astype(str)
                data_uji['Jalur Masuk'] = data_uji['Jalur Masuk'].astype(str)
                
                data_uji['Angkatan'] = data_uji['Angkatan'].astype(str)
                
                data_uji['Jalur Masuk'] = data_uji['Jalur Masuk'].apply(
                    lambda x: x.split('.')[0] if '.' in x else x
                )
                
                valid_prodi_codes = list(PROGRAM_STUDI_OPTIONS.keys())
                data_uji['Program Studi'] = data_uji['Program Studi'].apply(
                    lambda x: x if x in valid_prodi_codes else valid_prodi_codes[0]
                )
                              
                # Preprocessing
                X_uji_reshaped = preprocess_input_data(data_uji)

                # Prediksi
                predictions_prob = DO_model.predict(X_uji_reshaped).flatten()  

                # Menggabungkan hasil prediksi dengan data asli
                data_uji['Probabilitas'] = predictions_prob
                data_uji['Prediksi_Status'] = [
                    'Berpotensi DO' if prob >= 0.5 else 'Tidak Berpotensi DO' 
                    for prob in predictions_prob
                ]

                # Tampilkan hasil dengan format tabel yang benar
                st.write("Hasil Klasifikasi:")
                
                if 'NIM' in data_uji.columns:
                    data_uji['NIM'] = data_uji['NIM'].astype(str)
                if 'Angkatan' in data_uji.columns:
                    data_uji['Angkatan'] = data_uji['Angkatan'].astype(str)
                
                # Display the DataFrame
                st.dataframe(data_uji)

                # Simpan prediksi ke database
                total_mahasiswa = len(data_uji)
                berhasil_disimpan = 0
                gagal_disimpan = 0

                with engine.connect() as connection:
                    for _, row in data_uji.iterrows():
                        try:
                            academic_data = [
                                float(row['SKS7']) if pd.notna(row['SKS7']) else 0, 
                                float(row['IPKS7']) if pd.notna(row['IPKS7']) else 0,
                                float(row['IPS1']) if pd.notna(row['IPS1']) else 0,
                                float(row['IPS2']) if pd.notna(row['IPS2']) else 0,
                                float(row['IPS3']) if pd.notna(row['IPS3']) else 0,
                                float(row['IPS4']) if pd.notna(row['IPS4']) else 0,
                                float(row['IPS5']) if pd.notna(row['IPS5']) else 0,
                                float(row['IPS6']) if pd.notna(row['IPS6']) else 0,
                                float(row['IPS7']) if pd.notna(row['IPS7']) else 0
                            ]
                            
                            angkatan_str = str(row['Angkatan'])
                            
                            program_studi = str(row['Program Studi'])
                            if program_studi not in PROGRAM_STUDI_OPTIONS:
                                program_studi = list(PROGRAM_STUDI_OPTIONS.keys())[0]
                            
                            jalur_masuk = str(row['Jalur Masuk'])
                            
                            # Simpan prediksi
                            success, message = save_prediction_to_db(
                                engine,
                                str(row['Nama']), 
                                str(row['NIM']), 
                                angkatan_str,
                                jalur_masuk,
                                program_studi,
                                row['Prediksi_Status'], 
                                float(row['Probabilitas']),
                                academic_data
                            )
                            if success:
                                berhasil_disimpan += 1
                            else:
                                gagal_disimpan += 1
                                st.warning(f"Gagal menyimpan data untuk NIM {row['NIM']}: {message}")
                        except Exception as e:
                            gagal_disimpan += 1
                            st.warning(f"Error pada NIM {row['NIM']}: {str(e)}")

                # Tampilkan ringkasan
                if gagal_disimpan > 0:
                    st.warning(f"Dataset sebagian gagal disimpan, dari total {total_mahasiswa} mahasiswa, {berhasil_disimpan} berhasil disimpan dan {gagal_disimpan} gagal disimpan.")
                else:
                    st.success(f"Semua {total_mahasiswa} mahasiswa berhasil disimpan.")

            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")
                st.error(f"Detail error: {error_details}")

if __name__ == "__main__":
    run_prediction()