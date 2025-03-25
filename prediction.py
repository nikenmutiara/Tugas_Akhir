import streamlit as st
import numpy as np
import pickle
import pandas as pd
import tensorflow as tf
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError

# Load model dan scaler
DO_model = tf.keras.models.load_model('best_lstm_model5.h5')
scaler = pickle.load(open('Scaler5.pkl', 'rb'))

# Koneksi database
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
engine = create_engine(DATABASE_URL)

# Definisi kode program studi dan jalur masuk
PROGRAM_STUDI_OPTIONS = {
    '31201': 'Teknik Pertambangan',
    '33201': 'Teknik Geofisika',
    '34201': 'Teknik Geologi',
    '38201': 'Oseanografi',
    '44201': 'Matematika',
    '45201': 'Fisika',
    '46201': 'Biologi',
    '49201': 'Statistika',
    '47201': 'Kimia',
    '51201': 'Geografi',
    '54207': 'Bioteknologi',
    '59202': 'Ilmu Komputer'
}

JALUR_MASUK_OPTIONS = {
    '3': 'Penelusuran Minat dan Kemampuan (PMDK)',
    '4': 'Prestasi',
    '9': 'Program Internasional',
    '11': 'Program Kerjasama Perusahaan/Institusi/Pemerintah',
    '12': 'Seleksi Mandiri',
    '13': 'Ujian Masuk Bersama Lainnya',
    '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
    '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)'
}

def preprocess_data(data):
    """
    Preprocessing data untuk prediksi DO
    - Konversi numerik
    - Normalisasi
    - One-hot encoding
    """
    # Kolom yang dibutuhkan
    ips_columns = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
    fitur_lain = ['SKS7', 'IPKS7']

    # Konversi dan normalisasi data
    for col in ips_columns + fitur_lain:
        data[col] = pd.to_numeric(data[col], errors='coerce')

    # Tangani data tidak valid
    data.replace('#N/A', np.nan, inplace=True)
    data[ips_columns] = data[ips_columns].interpolate(method='linear', axis=1)
    data[ips_columns + fitur_lain] = data[ips_columns + fitur_lain].fillna(0.0)

    # One-hot encoding manual untuk program studi
    for code in PROGRAM_STUDI_OPTIONS.keys():
        data[f'Prodi_{code}'] = (data['Program Studi'] == code).astype(int)

    # One-hot encoding manual untuk jalur masuk
    for code in JALUR_MASUK_OPTIONS.keys():
        data[f'Jalur_{code}'] = (data['Jalur Masuk'] == code).astype(int)

    # Kolom fitur akhir
    feature_columns = (
        ips_columns + fitur_lain + 
        [f'Prodi_{code}' for code in PROGRAM_STUDI_OPTIONS.keys()] + 
        [f'Jalur_{code}' for code in JALUR_MASUK_OPTIONS.keys()]
    )

    # Pastikan semua kolom ada
    for col in feature_columns:
        if col not in data.columns:
            data[col] = 0

    return data[feature_columns].values, feature_columns

def predict_do_status(X, DO_model, scaler):
    """
    Prediksi status DO dengan model LSTM
    """
    # Normalisasi
    X_scaled = scaler.transform(X)

    # Reshape untuk LSTM
    input_sequence = np.zeros((X.shape[0], 7, X.shape[1]))
    for i in range(X.shape[0]):
        for timestep in range(7):
            input_sequence[i, timestep, :] = X_scaled[i, :]

    # Prediksi dengan threshold 0.3
    DO_predik = DO_model.predict(input_sequence)[:, 0]
    hasil = ['Berpotensi DO' if prob >= 0.3 else 'Tidak Berpotensi DO' for prob in DO_predik]

    return hasil, DO_predik

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    """
    Simpan prediksi ke database dengan error handling yang lebih baik
    """
    try:
        with engine.connect() as connection:
            # Default admin ID
            current_admin_id = st.session_state.get('user_id', 1)
            
            # Cek mahasiswa sudah ada atau belum
            mahasiswa_check_query = text("""
                SELECT id_mahasiswa 
                FROM `mahasiswa` 
                WHERE NIM = :nim
            """)
            mahasiswa_result = connection.execute(mahasiswa_check_query, {"nim": nim}).fetchone()

            # Jika mahasiswa belum ada, insert baru
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

            # Insert prediksi baru
            prediksi_query = text("""
                INSERT INTO `prediksi` 
                (id_mahasiswa, id_user, tanggal_prediksi, hasil_klasifikasi, probabilitas)
                VALUES (:id_mahasiswa, :id_user, CURDATE(), :hasil, :probabilitas)
            """)
            connection.execute(prediksi_query, {
                "id_mahasiswa": id_mahasiswa,
                "id_user": current_admin_id,
                "hasil": hasil,
                "probabilitas": float(probabilitas)
            })

            # Insert riwayat akademik jika belum ada
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
        st.error(f"Error saat menyimpan data: {str(e)}")
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
        jalur_masuk_code = st.selectbox('Jalur Masuk', options=list(JALUR_MASUK_OPTIONS.keys()), format_func=lambda x: f"{x} - {JALUR_MASUK_OPTIONS[x]}")
    
        # Input data akademik
        SKS7 = st.text_input('Total SKS Semester 7')
        IPKS7 = st.text_input('Indeks Prestasi Kumulatif Semester 7')
        IPS1 = st.text_input('Indeks Prestasi Semester 1')
        IPS2 = st.text_input('Indeks Prestasi Semester 2')
        IPS3 = st.text_input('Indeks Prestasi Semester 3')
        IPS4 = st.text_input('Indeks Prestasi Semester 4')
        IPS5 = st.text_input('Indeks Prestasi Semester 5')
        IPS6 = st.text_input('Indeks Prestasi Semester 6')
        IPS7 = st.text_input('Indeks Prestasi Semester 7')

        if st.button('Klasifikasi Status Mahasiswa'):
            try:
                # Siapkan data untuk prediksi
                data_manual = pd.DataFrame({
                    'Nama': [nama],
                    'NIM': [nim],
                    'Angkatan': [angkatan],
                    'Program Studi': [program_studi_code],
                    'Jalur Masuk': [jalur_masuk_code],
                    'SKS7': [SKS7],
                    'IPKS7': [IPKS7],
                    'IPS1': [IPS1],
                    'IPS2': [IPS2],
                    'IPS3': [IPS3],
                    'IPS4': [IPS4],
                    'IPS5': [IPS5],
                    'IPS6': [IPS6],
                    'IPS7': [IPS7]
                })

                # Preprocessing data
                X, feature_columns = preprocess_data(data_manual)

                # Prediksi
                hasil, probabilitas = predict_do_status(X, DO_model, scaler)

                # Tampilkan hasil
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi_code} - {PROGRAM_STUDI_OPTIONS[program_studi_code]}")
                st.write(f"Jalur Masuk: {jalur_masuk_code} - {JALUR_MASUK_OPTIONS[jalur_masuk_code]}")
                st.write(f"Hasil: {hasil[0]}")
                st.write(f"Probabilitas: {probabilitas[0]:.2f}")

                # Simpan ke database
                academic_data = [
                    float(SKS7), float(IPKS7), float(IPS1), float(IPS2), 
                    float(IPS3), float(IPS4), float(IPS5), float(IPS6), float(IPS7)
                ]
                success, message = save_prediction_to_db(
                    engine, nama, nim, angkatan, jalur_masuk_code, 
                    program_studi_code, hasil[0], probabilitas[0], academic_data
                )
                
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except ValueError as ve:
                st.error(f"Error konversi data: {str(ve)}")
            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")

    with tab2:
        # Upload file prediksi
        uploaded_file = st.file_uploader("Klasifikasi dari File (CSV atau Excel)", type=['csv', 'xlsx', 'xls'])

        if uploaded_file is not None:
            try:
                # Load file
                data = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)

                # Kolom yang dibutuhkan
                required_columns = ['Nama', 'NIM', 'Angkatan', 'Program Studi', 'Jalur Masuk', 
                                    'SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                
                # Validasi kolom
                missing_columns = [col for col in required_columns if col not in data.columns]
                if missing_columns:
                    st.error(f"Kolom berikut tidak ditemukan: {', '.join(missing_columns)}")
                    st.stop()

                # Preprocessing data
                X, feature_columns = preprocess_data(data)

                # Prediksi
                data['Hasil'], data['Probabilitas'] = predict_do_status(X, DO_model, scaler)

                # Tampilkan hasil
                st.write("Hasil Klasifikasi:", data)

                # Simpan prediksi ke database
                total_mahasiswa = len(data)
                berhasil_disimpan = 0
                gagal_disimpan = 0

                for _, row in data.iterrows():
                    academic_data = [
                        row['SKS7'], row['IPKS7'], row['IPS1'], row['IPS2'], 
                        row['IPS3'], row['IPS4'], row['IPS5'], row['IPS6'], row['IPS7']
                    ]
                    success, _ = save_prediction_to_db(
                        engine,
                        row['Nama'], row['NIM'], str(row['Angkatan']), 
                        str(row['Jalur Masuk']), str(row['Program Studi']),
                        row['Hasil'], row['Probabilitas'], academic_data
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

def main():
    run_prediction()

if __name__ == "__main__":
    main()