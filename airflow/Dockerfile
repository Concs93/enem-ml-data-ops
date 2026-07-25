FROM apache/airflow:3.3.0

# Venv separado para as dependencias do projeto.
#
# Airflow e dbt disputam versoes de jinja2, pydantic e outras bibliotecas
# comuns. Instalar os dois no mesmo ambiente resolve o conflito degradando
# um dos dois -- e o sintoma aparece longe da causa, num erro de template
# ou de validacao que nao faz sentido nenhum.
#
# Instalando a partir do requirements.txt do projeto, o pipeline orquestrado
# usa exatamente as mesmas versoes que voce roda a mao.
COPY requirements.txt /tmp/requirements.txt

RUN python -m venv /home/airflow/projeto-venv \
 && /home/airflow/projeto-venv/bin/pip install --no-cache-dir --upgrade pip \
 && /home/airflow/projeto-venv/bin/pip install --no-cache-dir \
      -r /tmp/requirements.txt
