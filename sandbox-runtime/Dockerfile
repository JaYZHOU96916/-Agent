FROM python:3.14.7-slim

ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib
RUN pip install --no-cache-dir pandas==3.0.5 pyarrow==25.0.1 duckdb==1.5.5 matplotlib==3.11.2
USER 65534:65534
WORKDIR /workspace
ENTRYPOINT ["python"]
