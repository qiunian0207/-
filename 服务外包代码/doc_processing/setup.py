from setuptools import setup, find_packages

setup(
    name="doc_processing",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        # Add actual dependencies if you want to enable pip install
    ],
    entry_points={
        "console_scripts": [
            "docproc=app.main:main"  # if main had a main() function
        ],
)
