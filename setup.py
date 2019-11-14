# coding: utf-8

import os
from distutils.command.build_py import build_py

from setuptools import find_packages, setup

with open("README.md") as file:
    long_description = file.read()

MAJOR = 0
MINOR = 1
MICRO = 0
ISRELEASED = True
VERSION = "%d.%d.%d" % (MAJOR, MINOR, MICRO)

# BEFORE importing distutils, remove MANIFEST. distutils doesn't properly
# update it when the contents of directories change.
if os.path.exists("MANIFEST"):
    os.remove("MANIFEST")


def _get_requirements_from_files(groups_files):
    groups_reqlist = {}

    for k, v in groups_files.items():
        with open(v, "r") as f:
            pkg_list = f.read().splitlines()
        groups_reqlist[k] = pkg_list

    return groups_reqlist


def setup_package():
    # get all file endings and copy whole file names without a file suffix
    # assumes nested directories are only down one level
    _groups_files = {
        "base": "requirements.txt",  # basic requirements
        "tests": "requirements_tests.txt",  # requirements for tests
        "docs": "requirements_docs.txt",  # requirements for building docs
    }

    reqs = _get_requirements_from_files(_groups_files)
    install_reqs = reqs.pop("base")

    setup(
        name="geosnap",
        version=VERSION,
        description="Geospatial Neighborhood Analysis Package.",
        long_description=long_description,
        long_description_content_type="text/markdown",
        maintainer="geosnap Developers",
        maintainer_email="pysal-dev@googlegroups.com",
        url="https://spatialucr.github.io/geosnap",
        download_url="https://pypi.python.org/pypi/geosnap",
        license="BSD",
        py_modules=["geosnap"],
        packages=find_packages(),
        setup_requires=["pytest-runner"],
        tests_require=["pytest"],
        keywords=["spatial statistics", "neighborhoods", "demography"],
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Science/Research",
            "Intended Audience :: Developers",
            "Intended Audience :: Education",
            "Topic :: Scientific/Engineering",
            "Topic :: Scientific/Engineering :: GIS",
            "License :: OSI Approved :: BSD License",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.5",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.7",
            "Programming Language :: Python :: 3.8",
        ],
        install_requires=install_reqs,
        cmdclass={"build_py": build_py},
        include_package_data=True,
        package_data={"geosnap": ["io/variables.csv", "io/lodes.csv", "io/stfips.csv"]},
        python_requires=">3.4",
    )


if __name__ == "__main__":
    setup_package()
