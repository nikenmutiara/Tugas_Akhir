import streamlit as st
import numpy as np
import pickle
import pandas as pd
import tensorflow as tf
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# 1. Load model dan scaler
DO_model = tf.keras.models.load_model('best_lstm_model5.h5')
scaler = pickle.load(open('Scaler5.pkl', 'rb'))

# 2. Setup koneksi database
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
engine = create_engine(DATABASE_URL)

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    try:
        with engine.connect() as connection:
            current_admin_id = st.session_state.get('user_id', 1)
            
            # Cek apakah mahasiswa sudah ada
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

            # Insert prediksi
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

            # Cek dan insert riwayat akademik
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
        # Opsi program studi dan jalur masuk
        program_studi_options = {
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
        
        jalur_masuk_options = {
            '12': 'Seleksi Mandiri',
            '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
            '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)'
        }

        # Input manual
        nama = st.text_input('Nama')
        nim = st.text_input('NIM')
        angkatan = st.text_input('Angkatan')
        
        program_studi_code = st.selectbox('Program Studi', options=list(program_studi_options.keys()), 
                                       format_func=lambda x: f"{x} - {program_studi_options[x]}")
        
        jalur_masuk_code = st.selectbox('Jalur Masuk', options=list(jalur_masuk_options.keys()), 
                                       format_func=lambda x: f"{x} - {jalur_masuk_options[x]}")
    
        # Input data akademik
        SKS7 = st.text_input('Total SKS Semester 7', value='0')
        IPKS7 = st.text_input('Indeks Prestasi Kumulatif Semester 7 (IPKS7)', value='0')
        IPS1 = st.text_input('Indeks Prestasi Semester 1 (IPS1)', value='0')
        IPS2 = st.text_input('Indeks Prestasi Semester 2 (IPS2)', value='0')
        IPS3 = st.text_input('Indeks Prestasi Semester 3 (IPS3)', value='0')
        IPS4 = st.text_input('Indeks Prestasi Semester 4 (IPS4)', value='0')
        IPS5 = st.text_input('Indeks Prestasi Semester 5 (IPS5)', value='0')
        IPS6 = st.text_input('Indeks Prestasi Semester 6 (IPS6)', value='0')
        IPS7 = st.text_input('Indeks Prestasi Semester 7 (IPS7)', value='0')

        if st.button('Klasifikasi Status Mahasiswa'):
            try:
                # Data numerik
                numerical_data = [
                    float(SKS7), float(IPKS7), float(IPS1), float(IPS2), float(IPS3),
                    float(IPS4), float(IPS5), float(IPS6), float(IPS7) 
                ]
                
                # One-hot encoding untuk program studi
                prodi_one_encoded = [1 if code == program_studi_code else 0 for code in program_studi_options.keys()]
                
                # One-hot encoding untuk jalur masuk
                jalur_masuk_encoded = [1 if code == jalur_masuk_code else 0 for code in jalur_masuk_options.keys()]
                
                # Gabungkan semua fitur (pastikan urutan sama dengan saat training)
                full_features = numerical_data + prodi_one_encoded + jalur_masuk_encoded
                
                # Normalisasi data
                features_normalized = scaler.transform([full_features])
                
                # Reshape untuk LSTM (1 timestep, 25 features)
                input_sequence = features_normalized.reshape((1, 1, 25))
                
                # Prediksi
                prediction_prob = DO_model.predict(input_sequence)[0][0]
                
                # Tentukan hasil (gunakan threshold 0.5)
                hasil = 'Berpotensi DO' if prediction_prob > 0.5 else 'Tidak Berpotensi DO'

                # Tampilkan hasil
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi_code} - {program_studi_options[program_studi_code]}")
                st.write(f"Jalur Masuk: {jalur_masuk_code} - {jalur_masuk_options[jalur_masuk_code]}")
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {prediction_prob:.4f}")

                # Simpan ke database
                success, message = save_prediction_to_db(
                    engine, nama, nim, angkatan, jalur_masuk_code, program_studi_code,
                    hasil, float(prediction_prob), numerical_data
                )
                
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except ValueError:
                st.error("Harap masukkan angka yang valid untuk semua input numerik!")
            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")
                st.error(f"Detail error: {str(e)}")
    
    with tab2:
        st.subheader("Prediksi dari File Excel/CSV")
    
        uploaded_file = st.file_uploader("Upload file data mahasiswa", type=['csv', 'xlsx'])
    
        if uploaded_file is not None:
            try:
                # Baca file
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                # Validasi kolom
                required_columns = ['Nama', 'NIM', 'Angkatan', 'Program Studi', 'Jalur Masuk',
                                'SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                
                missing_cols = [col for col in required_columns if col not in df.columns]
                if missing_cols:
                    st.error(f"Kolom berikut tidak ditemukan: {missing_cols}")
                    return
                
                # Konversi tipe data
                numeric_cols = ['SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                # Prediksi untuk setiap mahasiswa
                predictions = []
                probabilities = []
                
                for _, row in df.iterrows():
                    try:
                        # Data numerik - PERBAIKAN DI SINI (tanda [])
                        numerical_data = [float(row['SKS7']), float(row['IPKS7']), float(row['IPS1']), float(row['IPS2']), 
                            float(row['IPS3']), float(row['IPS4']), float(row['IPS5']), float(row['IPS6']), float(row['IPS7'])
                        ]
                        
                        # One-hot encoding program studi
                        prodi_encoded = [1 if str(code) == str(row['Program Studi']) else 0 
                                    for code in program_studi_options.keys()]
                        
                        # One-hot encoding jalur masuk
                        jalur_encoded = [1 if str(code) == str(row['Jalur Masuk']) else 0 
                                        for code in jalur_masuk_options.keys()]
                        
                        # Gabungkan fitur
                        full_features = numerical_data + prodi_encoded + jalur_encoded
                        
                        # Normalisasi
                        features_normalized = scaler.transform([full_features])
                        
                        # Reshape untuk LSTM
                        input_sequence = features_normalized.reshape((1, 1, 25))
                        
                        # Prediksi
                        prob = float(DO_model.predict(input_sequence)[0][0])  # Konversi ke float eksplisit
                        pred = 'Berpotensi DO' if prob > 0.5 else 'Tidak Berpotensi DO'
                        
                        probabilities.append(prob)
                        predictions.append(pred)
                    
                    except Exception as row_error:
                        st.error(f"Error processing row {row['NIM']}: {str(row_error)}")
                        probabilities.append(0.0)
                        predictions.append('Error')
                        continue
                
                # Tambahkan hasil ke dataframe
                df['Probabilitas'] = probabilities
                df['Prediksi'] = predictions
                
                # Tampilkan hasil
                st.write("Hasil Prediksi:")
                st.dataframe(df)
                
                # Simpan ke database
                success_count = 0
                for _, row in df.iterrows():
                    if row['Prediksi'] == 'Error':
                        continue
                        
                    academic_data = [
                        float(row['SKS7']), float(row['IPKS7']), float(row['IPS1']), float(row['IPS2']), float(row['IPS3']),
                        float(row['IPS4']), float(row['IPS5']), float(row['IPS6']), float(row['IPS7'])
                    ]
                    
                    success, _ = save_prediction_to_db(
                        engine,
                        str(row['Nama']),
                        str(row['NIM']),
                        str(row['Angkatan']),
                        str(row['Jalur Masuk']),
                        str(row['Program Studi']),
                        row['Prediksi'],
                        float(row['Probabilitas']),
                        academic_data
                    )
                    
                    if success:
                        success_count += 1
                
                st.success(f"Berhasil menyimpan {success_count} dari {len(df)} prediksi ke database")

            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")

if __name__ == '__main__':
    run_prediction()