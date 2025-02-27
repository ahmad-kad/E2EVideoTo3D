from setuptools import setup, find_packages

setup(
    name="photogrammetry-pipeline",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "opencv-python",
        "numpy",
        "pillow",
        "boto3",
        "s3fs",
        "pandas",
        "pyarrow",
        "pyspark",
        "findspark",
        "great-expectations",
        "evidently",
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "flake8",
            "jupyter",
        ],
    },
    python_requires=">=3.9",
    author="Your Name",
    author_email="your.email@example.com",
    description="An automated 3D photogrammetry pipeline",
    keywords="photogrammetry, 3d, computer-vision, spark, airflow",
    url="https://github.com/yourusername/photogrammetry-pipeline",
) 