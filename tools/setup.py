# pip install  -e .

import setuptools


setuptools.setup(
    name="dev-tools",
    version="1.0",
    packages=setuptools.find_packages(),
    install_requires=[
        "plac==1.3.5",
        "localstack-client==2.0",
        "python-hcl2==4.3.1",
        "boto3==1.26.90",
        "requests==2.30.0"
    ],
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "terraform-local = terraform.tflocal:script_main",
        ]
    },
)
