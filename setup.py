from setuptools import setup, find_packages

setup(
    name="DataversePython",
    version="0.1.4",
    description="A Dataverse client for Python",
    url="https://github.com/fabipfr/DataversePython",
    author="fabipfr",
    author_email="contact@fabianpfriem.com",
    packages=find_packages(),
    install_requires=[
        "requests >= 2.32.4",
        "pandas >= 2.2.3",
        "numpy >= 2.2.5",
        "msal >= 1.33.0"
    ],
    python_requires=">=3.10"    
)
