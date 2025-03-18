from setuptools import setup, find_packages

setup(
    name="pilot-progression",
    version="0.1.0",
    packages=find_packages(),  # Automatically finds packages
    install_requires=[
        "aerofiles@git+https://github.com/Turbo87/aerofiles.git",
        #"shortest-path", # use pip install -e ../shortest-path, or install from github (shortest-path@git+https://github.com/regio-beo/shortest-path.git)
        "numpy",
        "tqdm",
        "utm",
        "seaborn",
        "simplekml",
        "pandas"
    ],
)
