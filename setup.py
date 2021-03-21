from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(

    name='filetrans',

    version='0.0.1',

    description='A package for transferring files over the network with support for resuming broken transmissions.',

    long_description=long_description,
    long_description_content_type='text/markdown',

    url='https://github.com/sxwxs/fileTrans',

    author='sxwxs',

    author_email='sxwxs@msn.com',

    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',

        'Topic :: Utilities',

        'License :: OSI Approved :: MIT License',
        "Operating System :: OS Independent",
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    keywords='Transfering File with support for resuming broken transmissions',

    package_dir={'': 'src'},

    packages=find_packages(where='src'),

    python_requires='>=3.5',

    install_requires=[], 

    entry_points={  
        'console_scripts': [
            'filetrans=filetrans:main',
        ],
    },

    project_urls={ 
        'Bug Reports': 'https://github.com/sxwxs/fileTrans/issues',
        'Funding': 'https://i.loli.net/2019/12/28/pv8PUd4eKGyNDiV.png',
        # 'Say Thanks!': '',
        'Source': 'https://github.com/sxwxs/fileTrans',
    },
)