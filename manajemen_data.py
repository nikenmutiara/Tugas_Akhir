import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import time

def get_db_connection():
    try:
        DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
        #DATABASE_URL = "mysql+pymysql://sql7766198:u1VYyGNmaQ@sql7.freesqldatabase.com/sql7766198"
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        return engine
    except Exception as e:
        st.error(f"Kesalahan koneksi database: {e}")
        return None

def create_log_table(connection):
    query = text("""
    CREATE TABLE IF NOT EXISTS mahasiswa_logs (
        id_mahasiswa INT,
        aksi VARCHAR(50),
        data_lama TEXT,
        data_baru TEXT,
        waktu_perubahan DATETIME,
        aksi_user VARCHAR(255),
        PRIMARY KEY (id_mahasiswa, waktu_perubahan)
    )""")
    connection.execute(query)

def log_change(connection, id_mahasiswa, aksi, data_lama=None, data_baru=None, aksi_user=None):
    try:
        def validate_input(data):
            """Validasi dan format data input"""
            if data is None:
                return "Tidak ada data"
            
            # Konversi ke string yang aman
            if isinstance(data, dict):
                # Filter value yang tidak None dan konversi ke string
                filtered_data = {
                    str(k): str(v) if v is not None else "Tidak ada" 
                    for k, v in data.items()
                }
                return ', '.join([f"{k}: {v}" for k, v in filtered_data.items()])
            
            return str(data)

        # Validasi input kritis
        if id_mahasiswa is None:
            print("Error: ID Mahasiswa tidak boleh None")
            return False

        # Siapkan data logging yang valid
        log_data = {
            "id_mahasiswa": int(id_mahasiswa),  # Pastikan id_mahasiswa adalah integer
            "aksi": str(aksi or "AKSI_TIDAK_DIKETAHUI"),
            "data_lama": validate_input(data_lama),
            "data_baru": validate_input(data_baru),
            "aksi_user": str(aksi_user or "Sistem")
        }

        # Debug: Cetak data yang akan dilog
        print("Data Logging:")
        for key, value in log_data.items():
            print(f"{key}: {value}")

        # Query insert dengan validasi
        query = text("""
        INSERT INTO mahasiswa_logs 
        (id_mahasiswa, aksi, data_lama, data_baru, waktu_perubahan, aksi_user)
        VALUES 
        (:id_mahasiswa, :aksi, :data_lama, :data_baru, NOW(), :aksi_user)
        """)
        
        # Eksekusi dengan parameter yang sudah divalidasi
        result = connection.execute(query, log_data)

        # Konfirmasi log
        print(f"Log berhasil disimpan. Baris terpengaruh: {result.rowcount}")
        return True

    except Exception as e:
        import traceback
        print("Error dalam log_change:")
        traceback.print_exc()
        return False
    
def delete_mahasiswa(id_mahasiswa, engine):
    with engine.begin() as connection:
        try:
            # Verifikasi data mahasiswa
            verify_query = text("SELECT * FROM mahasiswa WHERE id_mahasiswa = :id")
            result = connection.execute(verify_query, {"id": id_mahasiswa})
            mahasiswa = result.fetchone()
            
            if not mahasiswa:
                return False, "Data mahasiswa tidak ditemukan"

            # Siapkan data lama untuk logging
            data_lama = {
                "Nama": mahasiswa[1],
                "NIM": mahasiswa[2],
                "Angkatan": str(mahasiswa[3]),
                "Program Studi": mahasiswa[4],
                "Jalur Masuk": mahasiswa[5]
            }

            # 1. Cek apakah ada data terkait di tabel riwayat_akademik
            check_related_query = text("SELECT COUNT(*) FROM riwayat_akademik WHERE id_mahasiswa = :id")
            related_count = connection.execute(check_related_query, {"id": id_mahasiswa}).scalar()
            
            if related_count > 0:
                # Opsi 1: Hapus data terkait terlebih dahulu (CASCADE delete)
                delete_related_query = text("DELETE FROM riwayat_akademik WHERE id_mahasiswa = :id")
                connection.execute(delete_related_query, {"id": id_mahasiswa})
                print(f"Menghapus {related_count} data terkait di riwayat_akademik")
                
                # Opsi lain: Periksa tabel prediksi juga
                check_prediksi_query = text("SELECT COUNT(*) FROM prediksi WHERE id_mahasiswa = :id")
                prediksi_count = connection.execute(check_prediksi_query, {"id": id_mahasiswa}).scalar()
                
                if prediksi_count > 0:
                    delete_prediksi_query = text("DELETE FROM prediksi WHERE id_mahasiswa = :id")
                    connection.execute(delete_prediksi_query, {"id": id_mahasiswa})
                    print(f"Menghapus {prediksi_count} data terkait di prediksi")

            # Logging penghapusan
            log_query = text("""
            INSERT INTO mahasiswa_logs 
            (id_mahasiswa, aksi, data_lama, data_baru, waktu_perubahan, aksi_user)
            VALUES 
            (:id_mahasiswa, :aksi, :data_lama, :data_baru, NOW(), :aksi_user)
            """)
            log_data = {
                "id_mahasiswa": id_mahasiswa,
                "aksi": "HAPUS",
                "data_lama": ', '.join([f"{k}: {v}" for k, v in data_lama.items()]),
                "data_baru": "Data mahasiswa dihapus",
                "aksi_user": "Sistem Manajemen Data"
            }

            try:
                log_result = connection.execute(log_query, log_data)
                print(f"Log berhasil disimpan. Baris terpengaruh: {log_result.rowcount}")
            except Exception as log_error:
                print(f"GAGAL MENYIMPAN LOG: {log_error}")
                import traceback
                traceback.print_exc()
                # Tetap lanjutkan proses penghapusan meskipun log gagal

            # Hapus data mahasiswa
            delete_query = text("DELETE FROM mahasiswa WHERE id_mahasiswa = :id")
            delete_result = connection.execute(delete_query, {"id": id_mahasiswa})

            if delete_result.rowcount > 0:
                return True, "Data berhasil dihapus beserta data terkait!"
            else:
                return False, "Gagal menghapus data mahasiswa"

        except Exception as e:
            import traceback
            traceback.print_exc()
            # Berikan pesan yang lebih jelas tentang apa yang menyebabkan error
            if "foreign key constraint fails" in str(e):
                return False, "Gagal menghapus: Data mahasiswa masih digunakan di tabel lain. Hapus data terkait terlebih dahulu."
            return False, f"Error saat menghapus data: {str(e)}"
        
# Jalur Masuk yang baru
jalur_masuk_options = {
    '12': 'Seleksi Mandiri',
    '14': 'Seleksi Nasional Berdasarkan Tes (SNBT)',
    '15': 'Seleksi Nasional Berdasarkan Prestasi (SNBP)',
    'Unknown': 'Tidak Diketahui'
}

# Program Studi yang baru
program_studi_options = {
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

hasil_klasifikasi_mapping = {
    0: "Tidak Berpotensi DO",
    1: "Berpotensi DO"
}

st.markdown("""
    <style>
    .content-container {
        display: flex;
        flex-direction: column;
        gap: 20px;
        padding: 20px;
    }
    .content-card {
        background: #F1F1F1;
        border-radius: 10px;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        padding: 20px;
        transition: transform 0.3s ease;
    }
    .content-card:hover {
        transform: translateY(-5px);
    }
    .content-card h4 {
        font-size: 20px;
        font-weight: 700;
        color: #333333;
        margin-bottom: 20px;
    }
    .content-card input, .content-card select {
        width: 100%;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
        border: 1px solid #ccc;
    }
    .content-card button {
        background-color: #007BFF;
        color: white;
        padding: 10px 20px;
        border-radius: 5px;
        border: none;
        cursor: pointer;
        transition: background-color 0.3s;
    }
    .content-card button:hover {
        background-color: #0056b3;
    }
    .log-card {
        border: 1px solid #ddd;
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
    }
    .log-update {
        border-left: 4px solid #ffc107;
    }
    .log-delete {
        border-left: 4px solid #dc3545;
    }
    </style>
""", unsafe_allow_html=True)

def manage_data_page():
    st.title("Manajemen Data Mahasiswa")
    
    engine = get_db_connection()
    if engine:
        connection = engine.connect()
        try:
            create_log_table(connection)
            
            # Fetch initial data
            query = text("""
                SELECT m.*, p.hasil_klasifikasi
                FROM mahasiswa m
                LEFT JOIN prediksi p ON m.id_mahasiswa = p.id_mahasiswa
            """)
            result = connection.execute(query)
            data_mahasiswa = pd.DataFrame(result.fetchall(), columns=result.keys())
            
            # Matikan format tampilan numerik pandas untuk menghindari pemisah ribuan
            pd.set_option('display.float_format', '{:.0f}'.format)
            
            # Convert ID mahasiswa and angkatan to string to avoid comma in display
            if 'id_mahasiswa' in data_mahasiswa.columns:
                data_mahasiswa['id_mahasiswa'] = data_mahasiswa['id_mahasiswa'].astype(str)
            
            if 'angkatan' in data_mahasiswa.columns:
                data_mahasiswa['angkatan'] = data_mahasiswa['angkatan'].astype(str)

            tab1, tab2, tab3 = st.tabs(["Input & Lihat Data", "Update/Hapus Data", "Riwayat Perubahan"])

            # Tab 1: Input & Lihat Data
            with tab1:
                # Input Data Section
                st.markdown("<div class='content-card'><h4>Input Data Mahasiswa</h4>", unsafe_allow_html=True)
                with st.form("input_data"):
                    nama = st.text_input("Nama", key="input_nama")
                    nim = st.text_input("NIM", key="input_nim")
                    
                    # Program Studi sebagai selectbox dengan kode dan nama
                    program_studi_kode = st.selectbox(
                        "Program Studi",
                        options=list(program_studi_options.keys()),
                        format_func=lambda x: f"{x} - {program_studi_options[x]}",
                        key="input_prodi"
                    )
                    
                    angkatan = st.number_input("Angkatan", min_value=2000, max_value=2100, key="input_tahun", format="%d")
                    
                    # Jalur Masuk sebagai selectbox dengan kode dan nama
                    jalur_masuk_kode = st.selectbox(
                        "Jalur Masuk", 
                        options=list(jalur_masuk_options.keys()),
                        format_func=lambda x: f"{x} - {jalur_masuk_options[x]}",
                        key="input_jalur"
                    )
                    
                    submit_button = st.form_submit_button("Submit")
                    
                    if submit_button:
                        try:
                            with engine.begin() as conn:
                                query = text("""
                                    INSERT INTO mahasiswa (Nama, NIM, program_studi, `Angkatan`, jalur_masuk)
                                    VALUES (:nama, :nim, :program_studi, :angkatan, :jalur_masuk)
                                """)
                                result = conn.execute(query, {
                                    "nama": nama,
                                    "nim": nim,
                                    "program_studi": program_studi_kode,  # Simpan kode program studi
                                    "angkatan": int(angkatan),  # Pastikan sebagai integer
                                    "jalur_masuk": jalur_masuk_kode  # Simpan kode jalur masuk
                                })
                                
                                last_id = result.lastrowid
                                data_baru = {
                                    "Nama": nama,
                                    "NIM": nim,
                                    "Program Studi": f"{program_studi_kode} - {program_studi_options[program_studi_kode]}",
                                    "Angkatan": int(angkatan),  # Pastikan sebagai integer
                                    "Jalur Masuk": f"{jalur_masuk_kode} - {jalur_masuk_options[jalur_masuk_kode]}"
                                }
                                log_change(conn, last_id, "INSERT", None, data_baru, "Data baru ditambahkan")
                                
                            st.success("Data Mahasiswa berhasil disimpan!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                # Bagian Lihat Data
                st.markdown("<div class='content-card'><h4>Lihat Data Mahasiswa</h4>", unsafe_allow_html=True)
                if not data_mahasiswa.empty:
                    # Tambahkan kolom tampilan dengan nama lengkap untuk Program Studi dan Jalur Masuk
                    data_display = data_mahasiswa.copy()
                    
                    # Fungsi untuk mendapatkan nama lengkap program studi
                    def get_prodi_name(kode):
                        if kode in program_studi_options:
                            return f"{kode} - {program_studi_options[kode]}"
                        return kode
                    
                    # Fungsi untuk mendapatkan nama lengkap jalur masuk
                    def get_jalur_name(kode):
                        if kode in jalur_masuk_options:
                            return f"{kode} - {jalur_masuk_options[kode]}"
                        return kode
                    
                    # Terapkan fungsi ke kolom yang relevan
                    if 'program_studi' in data_display.columns:
                        data_display['program_studi_display'] = data_display['program_studi'].astype(str).apply(get_prodi_name)
                    
                    if 'jalur_masuk' in data_display.columns:
                        data_display['jalur_masuk_display'] = data_display['jalur_masuk'].astype(str).apply(get_jalur_name)
                    
                    # Pastikan kolom numerik ditampilkan sebagai string untuk menghindari pemisah ribuan
                    numeric_columns = ['id_mahasiswa', 'angkatan', 'hasil_klasifikasi'] 
                    for col in numeric_columns:
                        if col in data_display.columns and data_display[col].notna().any():
                            data_display[col] = data_display[col].astype(str)
                    
                    st.dataframe(data_display)
                else:
                    st.info("Belum ada data mahasiswa")

            # Tab 2: Update/Hapus Data
            with tab2:
                if not data_mahasiswa.empty:
                    st.markdown("<div class='content-card'><h4>Update/Hapus Data Mahasiswa</h4>", unsafe_allow_html=True)
                    
                    # Konversi ID kembali ke int untuk selectbox
                    id_list = data_mahasiswa["id_mahasiswa"].tolist()
                    id_mahasiswa = st.selectbox("Pilih Mahasiswa", id_list)
                    
                    # Cari data berdasarkan ID yang dipilih
                    current_data = data_mahasiswa[data_mahasiswa["id_mahasiswa"] == id_mahasiswa].iloc[0].to_dict()

                    update_nama = st.text_input("Nama", current_data["nama"])
                    update_nim = st.text_input("NIM", current_data["NIM"])
                    
                    # Tampilkan program studi sebagai selectbox
                    current_prodi = str(current_data["program_studi"])
                    update_program_studi_kode = st.selectbox(
                        "Program Studi",
                        options=list(program_studi_options.keys()),
                        format_func=lambda x: f"{x} - {program_studi_options[x]}",
                        index=list(program_studi_options.keys()).index(current_prodi) if current_prodi in program_studi_options else 0,
                        key="update_prodi"
                    )
                    
                    # Pastikan angkatan ditampilkan sebagai integer
                    if isinstance(current_data["angkatan"], str):
                        current_angkatan = int(current_data["angkatan"])
                    else:
                        current_angkatan = current_data["angkatan"]
                        
                    update_angkatan = st.number_input("Angkatan", min_value=2000, max_value=2100, 
                                                     value=current_angkatan, format="%d")
                    
                    # Tampilkan jalur masuk sebagai selectbox
                    current_jalur = str(current_data["jalur_masuk"])
                    update_jalur_masuk_kode = st.selectbox(
                        "Jalur Masuk", 
                        options=list(jalur_masuk_options.keys()),
                        format_func=lambda x: f"{x} - {jalur_masuk_options[x]}",
                        index=list(jalur_masuk_options.keys()).index(current_jalur) if current_jalur in jalur_masuk_options else 0,
                        key="update_jalur"
                    )
                    
                    action_button = st.radio("Pilih aksi", ("Update", "Hapus"))

                    if action_button == "Update" and st.button("Update Data"):
                        try:
                            with engine.begin() as conn:
                                query = text("""
                                    UPDATE mahasiswa
                                    SET Nama = :nama, NIM = :nim, program_studi = :program_studi, `Angkatan` = :angkatan, jalur_masuk = :jalur_masuk
                                    WHERE id_mahasiswa = :id
                                """)
                                conn.execute(query, {
                                    "nama": update_nama,
                                    "nim": update_nim,
                                    "program_studi": update_program_studi_kode,
                                    "angkatan": int(update_angkatan),  # Pastikan sebagai integer
                                    "jalur_masuk": update_jalur_masuk_kode,
                                    "id": id_mahasiswa
                                })
                                
                                data_lama = {
                                    "Nama": current_data["nama"],
                                    "NIM": current_data["NIM"],
                                    "Program Studi": f"{current_data['program_studi']} - {program_studi_options.get(current_prodi, current_prodi)}",
                                    "Angkatan": int(current_angkatan),  # Pastikan sebagai integer
                                    "Jalur Masuk": f"{current_data['jalur_masuk']} - {jalur_masuk_options.get(current_jalur, current_jalur)}"
                                }
                                
                                data_baru = {
                                    "Nama": update_nama,
                                    "NIM": update_nim,
                                    "Program Studi": f"{update_program_studi_kode} - {program_studi_options[update_program_studi_kode]}",
                                    "Angkatan": int(update_angkatan),  # Pastikan sebagai integer
                                    "Jalur Masuk": f"{update_jalur_masuk_kode} - {jalur_masuk_options[update_jalur_masuk_kode]}"
                                }
                                
                                log_change(conn, id_mahasiswa, "UPDATE", data_lama, data_baru, "Data mahasiswa diperbarui")
                                
                            st.success("Data berhasil diperbarui!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

                    elif action_button == "Hapus" and st.button("Hapus Data"):
                        try:
                            # Pastikan ID dikonversi dengan benar
                            id_mahasiswa_int = int(id_mahasiswa) if isinstance(id_mahasiswa, str) else id_mahasiswa
                            success, message = delete_mahasiswa(id_mahasiswa_int, engine)                            
                            if success:
                                st.success(message)
                                time.sleep(1)  # Tunggu sebentar
                                st.rerun()
                            else:
                                st.error(message)
                        except Exception as e:
                            import traceback
                            traceback.print_exc()
                            st.error(f"Terjadi kesalahan: {str(e)}")

            # Tab 3: Riwayat Perubahan
            with tab3:
                # Pastikan mengambil semua log, tidak hanya yang terbatas
                query_logs = text("""
                    SELECT id_mahasiswa, aksi, data_lama, data_baru, waktu_perubahan, aksi_user
                    FROM mahasiswa_logs
                    ORDER BY waktu_perubahan DESC
                """)
                logs_result = connection.execute(query_logs)
                logs_data = pd.DataFrame(logs_result.fetchall(), columns=logs_result.keys())
                
                # Pastikan id_mahasiswa di logs tidak memiliki format koma
                if not logs_data.empty and 'id_mahasiswa' in logs_data.columns:
                    logs_data['id_mahasiswa'] = logs_data['id_mahasiswa'].astype(str)
                
                if not logs_data.empty:
                    st.dataframe(logs_data)
                else:
                    st.info("Belum ada riwayat perubahan.")
        finally:
            connection.close()
            
if __name__ == "__main__":
    # Kode ini hanya akan berjalan jika skrip dijalankan secara langsung
    manage_data_page()