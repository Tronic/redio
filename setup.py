from setuptools import setup, find_packages
from redio import __version__

setup(
    name="redio",
    author="L. Kärkkäinen",
    author_email="tronic@noreply.users.github.com",
    description="Redis async client for Trio",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Tronic/redio",
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    packages=find_packages(),
    keywords=[
        "Redis", "key-value store", "trio", "async", "database", "networking"
    ],
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: System :: Networking",
        "Framework :: Trio",
        "License :: OSI Approved :: MIT License",
        "License :: Public Domain",
        "Operating System :: OS Independent",
    ],
    python_requires = ">=3.7",
    install_requires = [
        "trio>=0.13",
    ],
    include_package_data = True,
)
