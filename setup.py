from setuptools import setup, find_packages
from redio import __version__

setup(
    name="redio",
    version=__version__,
    author="L. Kärkkäinen",
    author_email="tronic@noreply.users.github.com",
    description="Redis Trio client",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Tronic/python-redio",
    packages=find_packages(),
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "License :: Public Domain",
        "Operating System :: OS Independent",
    ],
    python_requires = ">=3.7",
    install_requires = [
        "trio",
    ],
    include_package_data = True,
)
