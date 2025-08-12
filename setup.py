from setuptools import setup, find_packages
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="DataversePython",
    version="1.0.0",
    description="A Dataverse client for Python",
    url="https://github.com/fabipfr/DataversePython",
    author="fabipfr",
    author_email="contact@fabianpfriem.com",
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "requests >= 2.32.4",
        "pandas >= 2.2.3",
        "numpy >= 2.2.5",
        "msal >= 1.33.0"
    ],
    python_requires=">=3.10"    
)
