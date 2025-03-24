from setuptools import setup, find_packages

setup(
    name="xhshow",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pycryptodome",
        "typeguard",
        "aiohttp",
        "pydantic",
        "curl_cffi",
    ],
    python_requires=">=3.12",
)