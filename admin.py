import streamlit as st
import bcrypt
from sqlalchemy import create_engine, text

def get_db_connection():
    try:
        DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
        #DATABASE_URL = "mysql+pymysql://sql7766198:u1VYyGNmaQ@sql7.freesqldatabase.com/sql7766198"
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        st.error(f"Kesalahan koneksi database: {e}")
        return None

def get_admin_info(username):
    engine = get_db_connection()
    if engine:
        with engine.connect() as connection:
            query = text("SELECT username, last_login FROM user WHERE username = :username")
            result = connection.execute(query, {"username": username}).fetchone()
            return result
    return None

def update_admin_password(username, new_password):
    engine = get_db_connection()
    if engine:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        with engine.connect() as connection:
            query = text("UPDATE user SET password = :password WHERE username = :username")
            connection.execute(query, {"password": hashed_password, "username": username})

def profile_page(username):
    st.title("Profil User")
    # Buat layout dengan kolom

    # Ambil informasi admin
    admin_info = get_admin_info(username)
    if admin_info:
        st.subheader("Informasi Akun")
        with st.container():
            st.text_input("Username", value=admin_info.username, disabled=True)
            last_login = admin_info.last_login if admin_info.last_login else 'Belum pernah login'
            st.text_input("Terakhir Login", value=last_login, disabled=True)
    

    st.subheader("Ganti Password")
    with st.form("change_password_form"):
        old_password = st.text_input("Password Lama", type="password")
        new_password = st.text_input("Password Baru", type="password")
        confirm_password = st.text_input("Konfirmasi Password Baru", type="password")
        submit = st.form_submit_button("Ubah Password")
            
        if submit:
            if new_password != confirm_password:
                st.error("Password baru dan konfirmasi password tidak cocok.")
            else:
                try:
                    engine = get_db_connection()
                    if engine:
                        with engine.connect() as connection:
                            query = text("SELECT password FROM user WHERE username = :username")
                            result = connection.execute(query, {"username": username}).fetchone()
                            if result and bcrypt.checkpw(old_password.encode('utf-8'), result[0].encode('utf-8')):
                                update_admin_password(username, new_password)
                                st.success("Password berhasil diubah.")
                            else:
                                st.error("Password lama salah.")
                except Exception as e:
                    st.error(f"Terjadi kesalahan: {e}")