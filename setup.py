import pathlib
from setuptools import find_packages, setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="chpy",
    version="0.0.6",
    description="Build networks from the Companies House API",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/specialprocedures/chpy",
    author="Ian Goodrich",
    # author_email="office@realpython.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=find_packages(exclude=["collections", "time", "math", "re", "os"]),

    include_package_data=True,
    # install_requires=["networkx", "pandas", "progressbar", "fuzzywuzzy",
    #                   "os", "requests", "math", "time", "collections", "re"]

)
