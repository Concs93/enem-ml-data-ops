{#
    Por padrao o dbt concatena o schema do profile com o custom schema do
    modelo: +schema: marts viraria "staging_marts". Isso existe para ambientes
    multiusuario (cada dev com seu prefixo); num projeto de um dev so polui.

    Aqui o custom schema e usado como esta. Sem +schema, nada muda: o modelo
    vai para o schema do profile (staging).
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
