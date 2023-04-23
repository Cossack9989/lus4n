from setuptools import setup, find_packages


setup(
    name='lus4n',
    packages=find_packages(),
    version='0.1',
    install_requires=[
        "networkx",
        "matplotlib",
        "xxhash",
        "tqdm",
        "loguru",
        "luaparser"
    ],
    entry_points={
        'console_scripts': [
            'lus4n=lus4n.cli:main'
        ]
    }
)