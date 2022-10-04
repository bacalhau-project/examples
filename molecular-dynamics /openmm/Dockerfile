FROM conda/miniconda3

RUN conda install -y -c conda-forge openmm

WORKDIR /project

COPY ./run_openmm_simulation.py /project

LABEL org.opencontainers.image.source https://github.com/bacalhau-project/examples

CMD ["python","run_openmm_simulation.py"]
