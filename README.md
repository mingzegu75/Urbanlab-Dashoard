# Urbanlab-Dashoard
Urbanlab Dashoard project
# 🏙️ NYC Affordable Housing Explorer

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Neon](https://img.shields.io/badge/Neon-00E599?style=for-the-badge&logo=postgresql&logoColor=black)

## 📖 Overview

**NYC Affordable Housing Explorer** is an interactive data dashboard designed to help New Yorkers navigate the complex landscape of affordable housing. 

Leveraging official data from **Local Law 44 (LL44)** and **HPD**, this application visualizes affordable building locations, analyzes rent distributions, and provides tools to help users find housing options that match their specific budget and income levels.

🚀 **Live Demo:** [Click here to launch the App](https://mingze.streamlit.app)

---

## ✨ Key Features

* **🗺️ Interactive Geospatial Map**
    * Visualizes thousands of affordable buildings using **Pydeck**.
    * Color-coded markers based on rent affordability (Green: Low Rent, Red: High Rent).
    * Tooltips displaying address, total units, and minimum rent details.

* **🔍 Advanced Search & Filtering**
    * **Borough Filter:** Focus on specific areas (Manhattan, Brooklyn, Queens, Bronx, Staten Island).
    * **Smart Rent Filter:** Define your exact monthly budget range.
    * **Address Search:** Instantly find buildings near specific locations or zip codes.

* **📊 Data Analytics & Insights**
    * **Unit Breakdown:** Analyze available unit types (Studio, 1-BR, 2-BR, etc.).
    * **Affordability Calculator:** Input your annual income to calculate potential monthly savings based on the 30% rent rule.
    * **Neighborhood Analysis:** Identify zip codes with the most affordable average rents.

* **💾 Open Data Access**
    * View detailed building lists in an interactive table.
    * Download the filtered dataset as a CSV file for offline analysis.

---

## 🛠️ Tech Stack

This project is built using a modern data stack:

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | **Streamlit** | The core web framework for the interactive dashboard. |
| **Visualization** | **Pydeck & Altair** | For geospatial mapping and statistical charting. |
| **Database** | **PostgreSQL (Neon)** | Serverless cloud database storing cleaned housing data. |
| **Spatial Engine** | **PostGIS** | Handles complex geometric queries and coordinate transformations. |
| **ORM** | **SQLAlchemy** | Manages secure database connections in Python. |

---

## 📂 Data Sources

This project utilizes public datasets provided by **NYC Open Data**:

1.  **HPD Affordable Housing Production:** Building-level data on affordable projects.
2.  **Local Law 44 (LL44):** Detailed rent and affordability data for specific units.
3.  **MapPLUTO:** Extensive land use and geographic data for NYC tax lots (used for building footprints).

---

## 🚀 How to Run Locally

To run this application on your local machine:

1.  **Clone the repository**
    ```bash
    git clone [https://github.com/your-username/nyc-housing-app.git](https://github.com/your-username/nyc-housing-app.git)
    cd nyc-housing-app
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Secrets**
    Create a file named `.streamlit/secrets.toml` in the project root directory and add your database credentials:
    ```toml
    [default]
    DB_USER = "your_neon_user"
    DB_PASSWORD = "your_neon_password"
    DB_HOST = "your_neon_host"
    DB_PORT = "5432"
    DB_NAME = "neondb"
    ```

4.  **Run the App**
    ```bash
    streamlit run streamlit_app.py
    ```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).

---

**Created by [Mingze Gu]**
