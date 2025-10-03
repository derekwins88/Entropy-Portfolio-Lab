from setuptools import setup, find_packages

setup(
    name='entropylab',
    version='1.0.0',
    author='Derek Wins',
    author_email='derekalexanderespinoza@gmail.com',
    description='Entropy-powered backtesting engine',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/derekwins88/entropylab',
    packages=find_packages(exclude=("tests", "docs", "examples")),
    install_requires=['pandas', 'numpy', 'matplotlib'],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.8',
)
