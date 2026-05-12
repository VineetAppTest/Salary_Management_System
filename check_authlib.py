import streamlit as st
import sys
import subprocess

st.title("WageWise Authlib Diagnostic")
st.write("Python version:", sys.version)
st.write("Streamlit version:", st.__version__)
st.subheader("pip show Authlib")
st.code(subprocess.getoutput("python -m pip show Authlib"))
st.subheader("pip list | auth")
st.code(subprocess.getoutput("python -m pip list | grep -i auth || true"))
st.info("If Authlib is shown above, deploy main file path back to app.py.")
