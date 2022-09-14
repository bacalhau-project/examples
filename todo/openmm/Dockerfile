FROM conda/miniconda3

RUN conda install -y -c conda-forge openmm

WORKDIR /project

COPY ./run_openmm_simulation.py /project
COPY ./2dri-processed.pdb /project

CMD ["python","run_openmm_simulation.py"]