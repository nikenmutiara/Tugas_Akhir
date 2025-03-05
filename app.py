import streamlit as st
from admin import profile_page
from auth import login_prompt, logout, welcome
from dashboard import show_dashboard
from prediction import run_prediction
from manajemen_data import manage_data_page

# Cek login
if "status" not in st.session_state:
    st.session_state.status = "unverified"

# Menampilkan form login jika belum login
if st.session_state.status != "verified":
    login_prompt()
    st.stop()

# Tampilkan halaman welcome jika sudah login
if st.session_state.status == "verified":
    welcome()

# Sidebar Menu
add_selectbox = st.sidebar.selectbox("select menu", ('Dashboard', 'Classification','Student Management', 'User Profile', 'Logout'))

if add_selectbox == "Dashboard":
    show_dashboard()

if add_selectbox == "Classification":
    run_prediction()

if add_selectbox == "Student Management":
    manage_data_page()

if add_selectbox == "User Profile":
    if "logged_in_username" in st.session_state:
        profile_page(st.session_state.logged_in_username)
    else:
        st.error("User session not found. Please login again.")

if add_selectbox == "Logout":
    logout()


