{% macro num(coluna) %}
    nullif(replace({{ coluna }}, ',', '.'), '')::numeric
{% endmacro %}

{% macro inteiro(coluna) %}
    nullif({{ coluna }}, '')::integer
{% endmacro %}

{% macro booleano(coluna) %}
    case when {{ coluna }} = '1' then true
         when {{ coluna }} = '0' then false
         else null end
{% endmacro %}