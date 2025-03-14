import streamlit as st
import pickle
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

# Load model and scaler
DO_model = pickle.load(open('DO_model.sav', 'rb'))  # Assumes keras model
scaler = pickle.load(open('Scaler.pkl', 'rb'))

# Database connection setup
DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
#DATABASE_URL = "mysql+pymysql://sql7766198:u1VYyGNmaQ@sql7.freesqldatabase.com/sql7766198"
engine = create_engine(DATABASE_URL)

def save_prediction_to_db(engine, nama, nim, tahun_masuk, jalur_masuk, hasil, probabilitas, ips_data):
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
                return False, "Admin tidak ditemukan"
            
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
                    (Nama, NIM, `Tahun Masuk`, `Jalur Masuk`)
                    VALUES (:nama, :nim, :tahun_masuk, :jalur_masuk)
                """)
                connection.execute(mahasiswa_query, {
                    "nama": nama, 
                    "nim": nim, 
                    "tahun_masuk": tahun_masuk, 
                    "jalur_masuk": jalur_masuk
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
                    (id_mahasiswa, ips_1, ips_2, ips_3, ips_4, ips_5, ips_6, ips_7, ipks_7)
                    VALUES (:id_mahasiswa, :ips_1, :ips_2, :ips_3, :ips_4, :ips_5, :ips_6, :ips_7, :ipks_7)
                """)
                connection.execute(riwayat_query, {
                    "id_mahasiswa": id_mahasiswa,
                    "ips_1": ips_data[0],
                    "ips_2": ips_data[1],
                    "ips_3": ips_data[2],
                    "ips_4": ips_data[3],
                    "ips_5": ips_data[4],
                    "ips_6": ips_data[5],
                    "ips_7": ips_data[6],
                    "ipks_7": ips_data[7]
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
        tahun_masuk = st.text_input('Tahun Masuk')
        jalur_masuk = st.text_input('Jalur Masuk')
    
        # Input data
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
                input_data = [
                    float(IPKS7), float(IPS1), float(IPS2), float(IPS3),
                    float(IPS4), float(IPS5), float(IPS6), float(IPS7)
                ]

                # Normalize the data
                input_normalized = scaler.transform([input_data])

                # Predict using the model
                DO_predik = DO_model.predict(input_normalized)[0][0]  # Assuming sigmoid activation

                # Determine prediction result
                hasil = 'Berpotensi DO' if DO_predik > 0.5 else 'Tidak Berpotensi DO'

                # Display the result
                st.subheader('Hasil Klasifikasi')
                st.write(f"Nama: {nama}")
                st.write(f"NIM: {nim}")
                st.write(f"Tahun Masuk: {tahun_masuk}")
                st.write(f"Jalur Masuk: {jalur_masuk}")
                st.write(f"Hasil: {hasil}")
                st.write(f"Probabilitas: {DO_predik:.2f}")

                # Simpan ke database dengan data riwayat akademik
                success, message = save_prediction_to_db(
                    engine, nama, nim, tahun_masuk, jalur_masuk, 
                    hasil, DO_predik, input_data
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

                # Validasi kolom
                required_columns = ['Nama', 'NIM', 'Tahun Masuk', 'Jalur Masuk', 'IPKS7', 'IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
                ips_columns = ['IPS1', 'IPS2', 'IPS3', 'IPS4', 'IPS5', 'IPS6', 'IPS7']
            
                if all(col in data.columns for col in required_columns):
                    #pembersihan untuk Jalur Masuk
                    data['Jalur Masuk'] = data['Jalur Masuk'].fillna('Unknown')

                    # Mengganti nilai '#N/A' dengan NaN agar dapat diinterpolasi
                    data[ips_columns + ['IPKS7']] = data[ips_columns + ['IPKS7']].replace('#N/A', pd.NA)

                    # Pastikan semua kolom numerik
                    data[ips_columns + ['IPKS7']] = data[ips_columns + ['IPKS7']].apply(pd.to_numeric, errors='coerce')

                    # Interpolasi horizontal untuk IPS1 hingga IPS7 & vertikal untuk kolom IPKS7
                    data[ips_columns] = data[ips_columns].interpolate(method='linear', axis=1)
                    data['IPKS7'] = data['IPKS7'].interpolate(method='index')

                    # Pastikan tidak ada NaN lagi setelah interpolasi
                    data[ips_columns + ['IPKS7']] = data[ips_columns + ['IPKS7']].fillna(0.0)

                    # Normalize the data
                    normalized_data = scaler.transform(data[ips_columns + ['IPKS7']])

                    # Predict using the model
                    DO_predik = DO_model.predict(normalized_data).flatten()  # Assuming sigmoid activation

                    # Add predictions to the data
                    data['Probabilitas'] = DO_predik
                    data['Hasil'] = ['Berpotensi DO' if prob > 0.18 else 'Tidak Berpotensi DO' for prob in DO_predik]

                    # Display the predictions
                    st.write("Hasil Klasifikasi:", data)

                    # Save predictions to database
                    total_mahasiswa = len(data)
                    berhasil_disimpan = 0
                    gagal_disimpan = 0

                    with engine.connect() as connection:
                        for _, row in data.iterrows():
                            ips_data = [
                                row['IPS1'], row['IPS2'], row['IPS3'], row['IPS4'], 
                                row['IPS5'], row['IPS6'], row['IPS7'], row['IPKS7']
                            ]
                            # Simpan prediksi dan cek duplikasi
                            success, message = save_prediction_to_db(
                                engine,
                                row['Nama'], 
                                row['NIM'], 
                                row['Tahun Masuk'], 
                                row['Jalur Masuk'],
                                row['Hasil'], 
                                row['Probabilitas'],
                                ips_data
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
            except Exception as e:
                st.error(f"Terjadi kesalahan saat memproses file: {str(e)}")