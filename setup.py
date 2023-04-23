from setuptools import setup, find_packages


setup(
    name='lus4n',
    packages=find_packages(),
    version='0.1',
    install_requires=[
        "networkx",
        "xxhash",
        "tqdm",
        "loguru",
        "luaparser",
        "pyvis"
    ],
    entry_points={
        'console_scripts': [
            'lus4n=lus4n.cli:main'
        ]
    }
)