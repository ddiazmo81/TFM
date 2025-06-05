import streamlit as st
from transformers import BertModel, BertTokenizer
from sklearn.ensemble import RandomForestClassifier
import joblib
import torch
import numpy as np

# ---------------------------
# Cargar modelo BERT y clasificador entrenado
# ---------------------------
@st.cache_resource
def load_model():
    tokenizer = BertTokenizer.from_pretrained('bert-base-multilingual-cased')  # ¡IMPORTANTE!
    bert = BertModel.from_pretrained('bert-base-multilingual-cased')            # ¡IMPORTANTE!
    clf = joblib.load('modelo_random_forest_entrenado.pkl')  # Asegúrate de que esta ruta sea válida
    return tokenizer, bert, clf

tokenizer, bert_model, clf = load_model()

# ---------------------------
# Función para extraer embedding del texto
# ---------------------------
def embed_text(text):
    tokens = tokenizer(text, return_tensors='pt', truncation=True, padding='max_length', max_length=512)
    with torch.no_grad():
        outputs = bert_model(**tokens)
    cls_embedding = outputs.last_hidden_state[:, 0, :]  # Extraemos el vector [CLS]
    return cls_embedding[0].numpy()

# ---------------------------
# Interfaz de usuario
# ---------------------------
st.title("🔍 Detector de textos generados por IA")
st.write("Sube un archivo de texto para analizar si fue escrito por una inteligencia artificial o por un humano.")

uploaded_file = st.file_uploader("📄 Sube tu archivo .txt", type=["txt"])

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8")
    st.text_area("📚 Texto analizado:", content, height=200)

    # Obtener embedding y hacer predicción
    embedding = embed_text(content)
    prediction = clf.predict([embedding])[0]

    st.markdown("---")
    st.subheader("🧠 Resultado")
    if prediction == "ia":
        st.error("❌ El texto parece haber sido generado por IA.")
    else:
        st.success("✅ El texto parece haber sido escrito por un humano.")