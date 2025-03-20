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
DO_model = tf.keras.models.load_model('model2.h5')
# Load scaler with pickle (this is correct)
scaler = pickle.load(open('Scaler2.pkl', 'rb'))

# Database connection setup
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
#DATABASE_URL = "mysql+pymysql://sql7766198:u1VYyGNmaQ@sql7.freesqldatabase.com/sql7766198"
engine = create_engine(DATABASE_URL)

def save_prediction_to_db(engine, nama, nim, angkatan, jalur_masuk, program_studi, hasil, probabilitas, academic_data):
    try:
        with engine.connect() as connection:
            # Get admin_id from session state
            current_admin_id = st.session_state.user_id
            
            # Check if admin exists
            admin_check = connection.execute(
                text("SELECT id_user FROM user WHERE id_user = :id_user"),
                {"id_user": current_admin_id}
            ).fetchone()
            
            if not admin_check:
                return False, "User tidak ditemukan"
            
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

            # Check for existing prediction
            prediksi_check_query = text("""
                SELECT COUNT(*) 
                FROM `prediksi` 
                WHERE id_mahasiswa = :id_mahasiswa AND tanggal_prediksi = CURDATE()
            """)
            prediksi_result = connection.execute(prediksi_check_query, {"id_mahasiswa": id_mahasiswa}).fetchone()

            # If prediction exists for today, return False
            if prediksi_result[0] > 0:
                return False, "Prediksi untuk mahasiswa ini sudah ada pada hari ini"

            # Insert new prediction
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
                    "ips_1": academic_data[1],  # IPS1
                    "ips_2": academic_data[2],  # IPS2
                    "ips_3": academic_data[3],  # IPS3
                    "ips_4": academic_data[4],  # IPS4
                    "ips_5": academic_data[5],  # IPS5
                    "ips_6": academic_data[6],  # IPS6
                    "ips_7": academic_data[7],  # IPS7
                    "ipks_7": academic_data[0], # IPKS7
                    "sks_7": academic_data[8]   # SKS7
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
        # Input manual
        nama = st.text_input('Nama')
        nim = st.text_input('NIM')
        angkatan = st.text_input('Angkatan')
        
        # Dropdown untuk jalur masuk
        jalur_masuk_options = ['SBMPTN', 'SNMPTN', 'Mandiri', 'Beasiswa', 'Lainnya']
        jalur_masuk = st.selectbox('Jalur Masuk', jalur_masuk_options)
        
        # Input Program Studi
        program_studi = st.text_input('Program Studi')
    
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
                # Validasi input manual
                input_numerical_data = [
                    float(SKS7), float(IPKS7), float(IPS1), float(IPS2), float(IPS3),
                    float(IPS4), float(IPS5), float(IPS6), float(IPS7) 
                ]
                
                # Encode jalur masuk jika diperlukan (one-hot encoding atau encoding lainnya)
                # Misalnya jika menggunakan One-Hot Encoding untuk jalur masuk:
                jalur_masuk_encoded = [1 if jalur == jalur_masuk else 0 for jalur in jalur_masuk_options]
                
                # Gabungkan semua fitur
                input_data = input_numerical_data + jalur_masuk_encoded + [program_studi]
                
                # Normalize the numerical data (sesuaikan dengan cara preprocessing yang digunakan saat training)
                # Catatan: Di sini asumsinya scaler hanya untuk data numerik, sesuaikan dengan preprocessing Anda
                numerical_normalized = scaler.transform([input_numerical_data])
                
                # Gabungkan data yang sudah dinormalisasi dengan fitur kategorik yang sudah diencoding
                # Untuk contoh ini, kita asumsikan hanya data numerik yang perlu dinormalisasi
                input_for_prediction = numerical_normalized
                
                # Predict using the model
                DO_predik = DO_model.predict(input_for_prediction)[0][0]  # Assuming sigmoid activation

                # Determine prediction result
                hasil = 'Berpotensi DO' if DO_predik > 0.5 else 'Tidak Berpotensi DO'

                # Display the result
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Angkatan: {angkatan}")
                st.write(f"Program Studi: {program_studi}")
                st.write(f"Jalur Masuk: {jalur_masuk}")
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {DO_predik:.2f}")

                # Simpan ke database dengan data riwayat akademik
                success, message = save_prediction_to_db(
                    engine, nama, nim, angkatan, jalur_masuk, program_studi,
                    hasil, DO_predik, input_numerical_data
                )
                if success:
                    st.success(message)
                else:
                    st.warning(message)

            except ValueError:
                st.error("Harap masukkan angka desimal yang valid untuk semua input!")
            except Exception as e:
                st.error(f"Terjadi kesalahan: {str(e)}")
    
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

                st.write("Data yang diunggah:", data.head())

                # Validasi kolom yang dibutuhkan
                required_columns = ['Nama', 'NIM', 'Angkatan', 'Program Studi', 'Jalur Masuk', 
                                   'SKS7', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                ips_columns = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
            
                if all(col in data.columns for col in required_columns):
                    # Pembersihan untuk kolom kategorik
                    data['Jalur Masuk'] = data['Jalur Masuk'].fillna('Unknown')
                    data['Program Studi'] = data['Program Studi'].fillna('Unknown')

                    # Mengganti nilai '#N/A' dengan NaN agar dapat diinterpolasi
                    numerical_columns = ips_columns + ['IPKS7', 'SKS7']
                    data[numerical_columns] = data[numerical_columns].replace('#N/A', pd.NA)

                    # Pastikan semua kolom numerik
                    data[numerical_columns] = data[numerical_columns].apply(pd.to_numeric, errors='coerce')

                    # Interpolasi horizontal untuk IPS1 hingga IPS7 & vertikal untuk kolom IPKS7 dan SKS7
                    data[ips_columns] = data[ips_columns].interpolate(method='linear', axis=1)
                    data[['IPKS7', 'SKS7']] = data[['IPKS7', 'SKS7']].interpolate(method='index')

                    # Pastikan tidak ada NaN lagi setelah interpolasi
                    data[numerical_columns] = data[numerical_columns].fillna(0.0)

                    # Proses data untuk prediksi
                    predictions = []
                    probabilities = []
                    
                    for _, row in data.iterrows():
                        # Siapkan data numerik
                        numerical_data = [
                            row['SKS7'], row['IPKS7'], row['IPS1'], row['IPS2'], row['IPS3'],
                            row['IPS4'], row['IPS5'], row['IPS6'], row['IPS7']
                        ]
                        
                        # Normalize menggunakan scaler (sesuaikan dengan cara preprocessing Anda)
                        numerical_normalized = scaler.transform([numerical_data])

                        # Pisahkan nilai IPS dari fitur lainnya
                        ips_values = numerical_normalized[0, 2:9]  # IPS1 sampai IPS7
                        static_features = numerical_normalized[0, :2]  # IPKS7 dan SKS7
                       
                        # Encode jalur masuk jika diperlukan (simplifkasi, sesuaikan dengan preprocessing Anda)
                        jalur_masuk_encoded = [1 if jalur == row['Jalur Masuk'] else 0 for jalur in jalur_masuk_options]
                        
                        # Gabungkan static_features dengan jalur_masuk_encoded
                        all_static_features = np.concatenate([static_features, jalur_masuk_encoded])
                        
                        # Buat array 3D untuk input LSTM
                        input_sequence = np.zeros((1, 7, 1 + len(all_static_features)))
                        
                        # Isi channel pertama dengan nilai IPS per semester
                        input_sequence[0, :, 0] = ips_values
                        
                        # Isi channel lainnya dengan fitur statis
                        for i in range(len(all_static_features)):
                            input_sequence[0, :, i+1] = all_static_features[i]
                        
                        
                        # Predict
                        prob = DO_model.predict(input_sequence)[0][0]
                        result = 'Berpotensi DO' if prob > 0.5 else 'Tidak Berpotensi DO'
                        
                        probabilities.append(prob)
                        predictions.append(result)
                    
                    # Tambahkan hasil ke dataframe
                    data['Probabilitas'] = probabilities
                    data['Hasil'] = predictions

                    # Display the predictions
                    st.write("Hasil Klasifikasi:", data)

                    # Save predictions to database
                    total_mahasiswa = len(data)
                    berhasil_disimpan = 0
                    gagal_disimpan = 0

                    with engine.connect() as connection:
                        for _, row in data.iterrows():
                            academic_data = [
                                row['SKS7'], row['IPKS7'], row['IPS1'], row['IPS2'], row['IPS3'], 
                                row['IPS4'], row['IPS5'], row['IPS6'], row['IPS7']
                            ]
                            # Simpan prediksi dan cek duplikasi
                            success, message = save_prediction_to_db(
                                engine,
                                row['nama'], 
                                row['NIM'], 
                                row['angkatan'], 
                                row['program_studi'],
                                row['jalur_masuk'],
                                row['Hasil'], 
                                row['Probabilitas'],
                                academic_data
                            )
                            if success:
                                berhasil_disimpan += 1
                            else:
                                gagal_disimpan += 1

                    # Tampilkan ringkasan hasil penyimpanan
                    if gagal_disimpan > 0:
                        st.warning(f"Dataset sudah ada didatabase, dari total {total_mahasiswa} mahasiswa, {berhasil_disimpan} berhasil disimpan dan {gagal_disimpan} gagal disimpan.")
                    else:
                        st.success(f"Semua {total_mahasiswa} mahasiswa berhasil disimpan.")
                else:
                    missing_columns = [col for col in required_columns if col not in data.columns]
                    st.error(f"File tidak memiliki semua kolom yang diperlukan. Kolom yang tidak ada: {', '.join(missing_columns)}")
            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")