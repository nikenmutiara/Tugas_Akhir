import streamlit as st
from sqlalchemy import create_engine, text
import pandas as pd

def get_db_connection():
    try:
        DATABASE_URL = "mysql+pymysql://root:@localhost/klasifikasi_do"
        #DATABASE_URL = "mysql+pymysql://sql7766198:u1VYyGNmaQ@sql7.freesqldatabase.com/sql7766198"
        engine = create_engine(DATABASE_URL)
        return engine
    except Exception as e:
        st.error(f"Kesalahan koneksi database: {e}")
        return None

def show_dashboard():
    st.title('Dashboard')
    
    # metrik model
    accuracy = 93
    precision = 81
    recall = 86
    f1_score = 84

    # custom CSS
    st.markdown("""
    <style>
    /* Existing metric styles */
    .metric-container {
        display: flex;
        justify-content: left;
        flex-wrap: wrap;
        gap: 20px;
        padding: 10px;
    }
    .metric-card {
        background: #BACBE0;
        border-radius: 8px;
        padding: 10px;
        width: calc(33.30% - 76px);
        min-width: 10px;
        box-shadow: 0 4px 8px rgba(1, 1, 1, 0.1);
        text-align: center;
        transition: transform 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-5px);
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #333333;
        margin: 3px 0;
    }
    .metric-icon-label {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    .metric-icon img {
        width: 20px;
        height: 20px;
    }
    .metric-label {
        font-size: 16px;
        font-weight: 700;
        color: #000000;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* New styles for dashboard containers */
    .dashboard-container {
        background: #BACBE0;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 8px rgba(1, 1, 1, 0.1);
    }
    
    /* Custom styles for Streamlit charts */
    .stChart {
        background-color: white !important;
        border-radius: 8px;
        padding: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    /* Style for progress bars */
    .stProgress > div > div > div {
        background-color: #4CAF50 !important;
    }
    
    /* Custom container headers */
    .container-header {
        font-size: 18px;
        font-weight: 600;
        color: #333333;
        margin-bottom: opx;
    }
    </style>
    """, unsafe_allow_html=True)

    metrics_html = f"""
    <div class="metric-container">
        <div class="metric-card">
            <div class="metric-icon-label">
                <div class="metric-icon">
                    <img src="https://img.icons8.com/fluency-systems-regular/50/accuracy.png" alt="accuracy" />
                </div>
                <div class="metric-label">Accuracy</div>
            </div>
            <div class="metric-value">{accuracy}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-icon-label">
                <div class="metric-icon">
                    <img src="https://img.icons8.com/fluency-systems-regular/50/bar-chart.png" alt="bar-chart" />
                </div>
                <div class="metric-label">Precision</div>
            </div>
            <div class="metric-value">{precision}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-icon-label">
                <div class="metric-icon">
                    <img src="https://img.icons8.com/fluency-systems-regular/50/circus-tent.png" alt="circus-tent" />
                </div>
                <div class="metric-label">Recall</div>
            </div>
            <div class="metric-value">{recall}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-icon-label">
                <div class="metric-icon">
                    <img src="https://img.icons8.com/fluency-systems-regular/50/scales.png" alt="scales" />
                </div>
                <div class="metric-label">F1-Score</div>
            </div>
            <div class="metric-value">{f1_score}%</div>
        </div>
    </div>
    """
    
    st.markdown(metrics_html, unsafe_allow_html=True)
    st.markdown("---")

    # 2 kolom
    col1, col2 = st.columns([1, 2.5])

    with col1:
        container_content = f"""
        <div class="dashboard-container">
            <div class="container-header">Jumlah Mahasiswa</div>
            <div style='text-align: center;'>
        """
        st.markdown(container_content, unsafe_allow_html=True)
        st.image('gambar/logo5.png', width=150)
        
        engine = get_db_connection()
        if engine:
            with engine.connect() as connection:
                query = text("SELECT COUNT(*) FROM mahasiswa")
                result = connection.execute(query).fetchone()
                total_data = result[0] if result else 0
                st.markdown(f"<p style='font-size: 50px; font-weight: bold; text-align: left;'>{total_data}</p>", unsafe_allow_html=True)
        
        st.markdown("</div></div>", unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="dashboard-container">
            <div class="container-header">Grafik Hasil Klasifikasi Mahasiswa</div>
        """, unsafe_allow_html=True)
        
        engine = get_db_connection()
        if engine:
            with engine.connect() as connection:
                query = text("""
                    SELECT hasil_klasifikasi, COUNT(id_prediksi) AS jumlah
                    FROM prediksi
                    JOIN mahasiswa ON prediksi.id_mahasiswa = mahasiswa.id_mahasiswa
                    GROUP BY hasil_klasifikasi
                """)
                data = pd.DataFrame(connection.execute(query).fetchall(), columns=['Status', 'Jumlah'])
                st.bar_chart(data.set_index('Status'))
        
        st.markdown("</div>", unsafe_allow_html=True)

    container_start = """
    <div class="dashboard-container">
        <div class="container-header">Jumlah Mahasiswa Berdasarkan Angkatan</div>
        <div class="progress-container">
    """
    st.markdown(container_start, unsafe_allow_html=True)
    
    engine = get_db_connection()
    if engine:
        with engine.connect() as connection:
            query = text("""
                SELECT `angkatan`, COUNT(*) as jumlah
                FROM mahasiswa
                GROUP BY `angkatan`
                ORDER BY `angkatan`
            """)
            year_data = pd.DataFrame(connection.execute(query).fetchall(), columns=['Tahun', 'Jumlah'])
            
            max_students = year_data['Jumlah'].max()
            for _, row in year_data.iterrows():
                percentage = (row['Jumlah'] / max_students) * 100
                st.markdown(f"<div style='margin-bottom: 15px;'><strong>Tahun {row['Tahun']}</strong></div>", unsafe_allow_html=True)
                st.progress(percentage / 100)
                st.markdown(f"<div style='margin-bottom: 20px;'>Jumlah Mahasiswa: {row['Jumlah']}</div>", unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)