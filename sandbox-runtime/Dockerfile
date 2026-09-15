FROM python:3.11-slim

ENV OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/matplotlib
RUN pip install --no-cache-dir pandas==2.2.3 pyarrow==20.0.0 duckdb==1.3.2 matplotlib==3.10.3
USER 65534:65534
WORKDIR /workspace
ENTRYPOINT ["python"]
