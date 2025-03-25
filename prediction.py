import streamlit as st
import numpy as np
import pickle
import pandas as pd
import tensorflow as tf
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Load model correctly using Keras/TensorFlow (not pickle)
DO_model = tf.keras.models.load_model('best_lstm_model5.h5')
# Load scaler with pickle (this is correct)
scaler = pickle.load(open('Scaler5.pkl', 'rb'))

# Database connection setup
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
engine = create_engine(DATABASE_URL)

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    try:
        with engine.connect() as connection:
            # Pastikan selalu ada user_id di session state
            current_admin_id = st.session_state.get('user_id', 1)  # Default ke 1 jika tidak ada
            
            # Check if student exists
            mahasiswa_check_query = text("""
                SELECT id_mahasiswa 
                FROM `mahasiswa` 
                WHERE NIM = :nim
            """)
            mahasiswa_result = connection.execute(mahasiswa_check_query, {"nim": nim}).fetchone()

            # If student doesn't exist, insert new student
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
                # Get the newly inserted student's ID
                mahasiswa_result = connection.execute(mahasiswa_check_query, {"nim": nim}).fetchone()

            id_mahasiswa = mahasiswa_result[0]

            # Hapus logika pengecekan prediksi harian
            # Insert new prediction tanpa batasan
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

            # Check and insert academic history
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

            # Commit the transaction
            connection.commit()
            return True, "Data berhasil disimpan"
    
    except Exception as e:
        return False, f"Error: {str(e)}"

def run_prediction():
    st.title('Klasifikasi Mahasiswa Berpotensi DO')

    tab1, tab2 = st.tabs(["Klasifikasi Manual", "Unggah File"])

    with tab1:
        # Program studi and jalur masuk definitions
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
            '3': 'Penelusuran Minat dan Kemampuan (PMDK)',
            '4': 'Prestasi',
            '9': 'Program Internasional',
            '11': 'Program Kerjasama Perusahaan/Institusi/Pemerintah',
            '12': 'Seleksi Mandiri',
            '13': 'Ujian Masuk Bersama Lainnya',
            '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
            '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)'
        }

        # Input manual
        nama = st.text_input('Nama')
        nim = st.text_input('NIM')
        angkatan = st.text_input('Angkatan')
        
        program_studi_code = st.selectbox('Program Studi', options=list(program_studi_options.keys()), format_func=lambda x: f"{x} - {program_studi_options[x]}")
        program_studi = program_studi_code  # Store the code in the database
        
        jalur_masuk_code = st.selectbox('Jalur Masuk', options=list(jalur_masuk_options.keys()), format_func=lambda x: f"{x} - {jalur_masuk_options[x]}")
        jalur_masuk = jalur_masuk_code  # Store the code in the database
    
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
                # Definisikan numerical_data di sini
                numerical_data = [
                    float(SKS7), float(IPKS7), float(IPS1), float(IPS2), float(IPS3),
                    float(IPS4), float(IPS5), float(IPS6), float(IPS7) 
                ]
                
                # Get program studi code list for one-hot encoding
                program_studi_codes = list(program_studi_options.keys())

                # Get jalur masuk code list for one-hot encoding
                jalur_masuk_codes = list(jalur_masuk_options.keys())
                
                # One-hot encoding untuk program studi dan jalur masuk
                prodi_one_encoded = [1 if code == program_studi_code else 0 for code in program_studi_codes]
                jalur_masuk_encoded = [1 if code == jalur_masuk_code else 0 for code in jalur_masuk_codes]
                
                # Gabungkan semua fitur dalam urutan yang sama dengan saat training
                # Pastikan total fitur tepat 25
                full_features = (
                    numerical_data +  # 9 features of academic data 
                    prodi_one_encoded[:12] +  # 12 features for program studi one-hot
                    jalur_masuk_encoded[:4]  # 4 features for jalur masuk one-hot
                )

                # Pastikan jumlah fitur tepat 25
                assert len(full_features) == 25, f"Expected 25 features, got {len(full_features)}"

                # Normalisasi semua data numerik
                numerical_normalized = scaler.transform([full_features])
                                   
                # Buat array 3D untuk input LSTM: (1, 7, 25)
                input_sequence = np.zeros((1, 7, 25))
                                
                # Replikasi fitur kategorik ke semua timestep
                for timestep in range(7):
                    input_sequence[0, timestep, :] = numerical_normalized[0, :]

                # Predict menggunakan model dengan input yang sudah benar bentuknya
                DO_predik = DO_model.predict(input_sequence)[0][0]

                # Determine prediction result
                # PENTING: Ubah logika klasifikasi sesuai kebutuhan spesifik Anda
                # Contoh: Lebih rendah threshold atau sesuaikan dengan kebutuhan model
                hasil = 'Berpotensi DO' if DO_predik >= 0.3 else 'Tidak Berpotensi DO'

                # Display the result
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi_code} - {program_studi_options[program_studi_code]}")
                st.write(f"Jalur Masuk: {jalur_masuk_code} - {jalur_masuk_options[jalur_masuk_code]}")
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {DO_predik:.2f}")

                # Simpan ke database dengan data riwayat akademik
                success, message = save_prediction_to_db(
                    engine, nama, nim, angkatan, jalur_masuk, program_studi,
                    hasil, DO_predik, numerical_data
                )
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except ValueError:
                st.error("Harap masukkan angka desimal yang valid untuk semua input!")
            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")
    
    # Bagian dalam fungsi run_prediction(), fokus pada tab file upload

    with tab2:
        # Upload file prediksi
        uploaded_file = st.file_uploader("Klasifikasi dari File (CSV atau Excel)", type=['csv', 'xlsx', 'xls'])

        if uploaded_file is not None:
            try:
                # Load file
                if uploaded_file.name.endswith('.csv'):
                    data = pd.read_csv(uploaded_file)
                else:
                    data = pd.read_excel(uploaded_file)

                # Definisikan kolom yang dibutuhkan
                required_columns = ['Nama', 'NIM', 'Angkatan', 'Program Studi', 'Jalur Masuk', 
                                    'SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                
                # Validasi kolom
                for col in required_columns:
                    if col not in data.columns:
                        st.error(f"Kolom {col} tidak ditemukan dalam file!")
                        st.stop()

                # Konversi data string menjadi numerik
                ips_columns = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                numeric_columns = ['SKS7', 'IPKS7'] + ips_columns

                # Tangani data yang tidak valid
                for col in numeric_columns:
                    data[col] = pd.to_numeric(data[col], errors='coerce')
                
                # Ganti NaN dengan median atau cara lain yang sesuai
                for col in numeric_columns:
                    data[col].fillna(data[col].median(), inplace=True)

                # Definisi kode untuk program studi dan jalur masuk
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
                    '3': 'Penelusuran Minat dan Kemampuan (PMDK)',
                    '4': 'Prestasi',
                    '9': 'Program Internasional',
                    '11': 'Program Kerjasama Perusahaan/Institusi/Pemerintah',
                    '12': 'Seleksi Mandiri',
                    '13': 'Ujian Masuk Bersama Lainnya',
                    '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
                    '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)'
                }

                # Validasi kode program studi dan jalur masuk
                def validate_and_convert_code(code, options):
                    # Coba konversi jika code adalah string angka
                    if isinstance(code, str):
                        code = code.strip()
                    
                    # Periksa apakah code ada di opsi
                    if str(code) in options:
                        return str(code)
                    
                    # Jika tidak, coba ambil kode pertama yang cocok
                    for opt_code in options.keys():
                        if str(opt_code) == str(code) or str(opt_code) in str(code):
                            return str(opt_code)
                    
                    # Jika tidak ditemukan, gunakan default atau pertama
                    return list(options.keys())[0]

                # Konversi kode program studi dan jalur masuk
                data['Program Studi'] = data['Program Studi'].apply(
                    lambda x: validate_and_convert_code(x, program_studi_options)
                )
                data['Jalur Masuk'] = data['Jalur Masuk'].apply(
                    lambda x: validate_and_convert_code(x, jalur_masuk_options)
                )

                # Prediksi untuk setiap baris
                predictions = []
                probabilities = []

                for _, row in data.iterrows():
                    # Siapkan data numerik
                    numerical_data = [
                        row['SKS7'], row['IPKS7'], row['IPS1'], row['IPS2'], row['IPS3'],
                        row['IPS4'], row['IPS5'], row['IPS6'], row['IPS7']
                    ]
                    
                    # One-hot encoding untuk program studi dan jalur masuk
                    program_studi_codes = list(program_studi_options.keys())
                    jalur_masuk_codes = list(jalur_masuk_options.keys())
                    
                    prodi_one_encoded = [1 if code == row['Program Studi'] else 0 for code in program_studi_codes]
                    jalur_masuk_encoded = [1 if code == row['Jalur Masuk'] else 0 for code in jalur_masuk_codes]
                    
                    # Gabungkan fitur
                    full_features = (
                        numerical_data +  # 9 fitur akademik
                        prodi_one_encoded[:12] +  # 12 fitur one-hot program studi
                        jalur_masuk_encoded[:4]  # 4 fitur one-hot jalur masuk
                    )

                    # Normalisasi
                    numerical_normalized = scaler.transform([full_features])

                    # Buat input sequence LSTM
                    input_sequence = np.zeros((1, 7, 25))
                    for timestep in range(7):
                        input_sequence[0, timestep, :] = numerical_normalized[0, :]
                    
                    # Prediksi
                    DO_predik = DO_model.predict(input_sequence)[0][0]
                    
                    # PENTING: Sesuaikan threshold prediksi
                    # Gunakan threshold yang lebih rendah untuk sensitivitas tinggi
                    hasil = 'Berpotensi DO' if DO_predik >= 0.3 else 'Tidak Berpotensi DO'
                    
                    probabilities.append(DO_predik)
                    predictions.append(hasil)
                
                # Tambahkan hasil prediksi ke dataframe
                data['Probabilitas'] = probabilities
                data['Hasil'] = predictions

                # Tampilkan hasil
                st.write("Hasil Klasifikasi:", data)

                # Simpan prediksi ke database
                total_mahasiswa = len(data)
                berhasil_disimpan = 0
                gagal_disimpan = 0

                with engine.connect() as connection:
                    for _, row in data.iterrows():
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
                            row['Hasil'], 
                            row['Probabilitas'],
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