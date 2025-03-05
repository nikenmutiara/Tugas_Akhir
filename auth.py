import streamlit as st
import bcrypt
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import time

def get_db_connection():
    try:
        DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        return Session()
    except Exception as e:
        st.error(f"Kesalahan koneksi database: {e}")
        return None

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(input_password, stored_hash):
    return bcrypt.checkpw(input_password.encode('utf-8'), stored_hash if isinstance(stored_hash, bytes) else stored_hash.encode('utf-8'))

def check_login(username, password):
    session = get_db_connection()
    if session:
        try:
            query = text("SELECT * FROM user WHERE username = :username")
            result = session.execute(query, {"username": username}).fetchone()
            if result and check_password(password, result.password):
                update_query = text("UPDATE user SET last_login = NOW() WHERE username = :username")
                session.execute(update_query, {"username": username})
                session.commit()
                st.session_state.logged_in_username = username
                st.session_state.user_id = result.id_user
                st.session_state.status = "verified"
                return True
        except Exception as e:
            st.error(f"Terjadi kesalahan saat memeriksa login: {str(e)}")
        finally:
            session.close()
    return False

def login_prompt():
    st.title("Welcome")
    st.write("Welcome back! Please login to your account")

    # Initialize session states if they don't exist
    if 'logged_in_username' not in st.session_state:
        st.session_state.logged_in_username = None
    if 'status' not in st.session_state:
        st.session_state.status = None

    tab1, tab2 = st.tabs(["Login", "User Registration"])
    
    with tab1:
        username = st.text_input("Username:", key="login_username")
        password = st.text_input("Password:", key="login_password", type="password")
        
        if st.button("Login"):
            if not username or not password:
                st.warning("Username and password must not be empty.")
            else:
                if check_login(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.warning("Incorrect username or password. Please try again.")

    with tab2:
        new_username = st.text_input("Username:", key="new_username")
        new_password = st.text_input("Password:", key="new_password", type="password")
        confirm_password = st.text_input("Confirm Password:", key="confirm_password", type="password")
        
        if st.button("Registration"):
            if not new_username or not new_password or not confirm_password:
                st.warning("All fields must be filled.")
                return

            if new_password != confirm_password:
                st.warning("Passwords do not match.")
                return

            if len(new_password) < 6:
                st.warning("Password must be at least 6 characters long.")
                return

            session = get_db_connection()
            if session:
                try:
                    check_query = text("SELECT * FROM user WHERE username = :username")
                    existing_user = session.execute(check_query, {"username": new_username}).fetchone()
                    if existing_user:
                        st.warning("Username already exists. Please choose another.")
                        return

                    hashed_password = hash_password(new_password)
                    insert_query = text("""INSERT INTO user (username, password) VALUES (:username, :password)""")
                    session.execute(insert_query, {"username": new_username, "password": hashed_password})
                    session.commit()
                    st.success("Registration successful! You can now log in.")
                except Exception as e:
                    st.error(f"Registration failed: {str(e)}")
                finally:
                    session.close()

def welcome():
    if 'login_shown' not in st.session_state:
        st.session_state.login_shown = False
        
    if not st.session_state.login_shown:
        placeholder = st.empty()
        placeholder.success("Login successful!")
        time.sleep(1)
        placeholder.empty()
        st.session_state.login_shown = True

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()