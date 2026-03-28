from setuptools import find_packages, setup


setup(
    name="doc_processing",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit",
        "pandas",
        "openpyxl",
        "python-docx",
        "pypdf",
        "pillow",
    ],
)
