from setuptools import setup, find_packages

setup(
    name="xhshow",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "aiofiles~=24.1.0",
        "beautifulsoup4~=4.13.3",
        "demjson3>=3.0.6",
        "dotenv>=0.9.9",
        "loguru~=0.7.2",
        "lxml~=5.3.0",
        "openai>=1.68.2",
        "openpyxl~=3.1.5",
        "pandas~=2.2.3",
        "pillow>=11.1,<11.3",
        "pycryptodome>=3.21,<3.24",
        "requests~=2.32.3",
        "typeguard~=4.4.1",
        "aiohttp",
        "pydantic",
        "curl_cffi",
    ],
    python_requires=">=3.12",
)